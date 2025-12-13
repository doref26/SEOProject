from __future__ import annotations

import ast
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer

from .llm_providers.ollama_client import OllamaError, ollama_chat, ollama_embed
from .llm_providers.gemini_client import GeminiError, gemini_chat


class RAGConfigError(Exception):
    """Configuration or runtime issues specific to the RAG layer."""


class RAGConfig(BaseModel):
    """
    Configuration for the RAG layer, read from environment variables.

    This keeps all external dependencies (OpenAI, vector DB) in one place and
    makes it easy to swap providers later.
    """

    openai_api_key: str = Field(
        ...,
        description="API key for OpenAI (env: OPENAI_API_KEY). May be empty if not using OpenAI.",
    )
    openai_model: str = Field(
        default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        description="Chat/completions model used for reasoning.",
    )
    embedding_model: str = Field(
        default_factory=lambda: os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        description="Embedding model used for retrieval queries.",
    )

    qdrant_url: Optional[str] = Field(
        default_factory=lambda: os.getenv("QDRANT_URL"),
        description="Qdrant endpoint URL (env: QDRANT_URL). If not set, retrieval is skipped.",
    )
    qdrant_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("QDRANT_API_KEY"),
        description="Qdrant API key (env: QDRANT_API_KEY).",
    )
    qdrant_collection: str = Field(
        default_factory=lambda: os.getenv("QDRANT_COLLECTION", "seo_knowledge"),
        description="Qdrant collection name holding SEO knowledge chunks.",
    )
    max_passages: int = Field(
        default_factory=lambda: int(os.getenv("RAG_MAX_PASSAGES", "6")),
        ge=1,
        le=16,
    )
    llm_provider: str = Field(
        default_factory=lambda: os.getenv("LLM_PROVIDER", "openai"),
        description="LLM provider: 'openai' (default), 'ollama', or 'gemini'.",
    )
    local_llm_model: str = Field(
        default_factory=lambda: os.getenv("LOCAL_LLM_MODEL", "llama3.1"),
        description="Local LLM model name for Ollama (e.g. llama3.1).",
    )
    embedding_backend: str = Field(
        default_factory=lambda: os.getenv("EMBEDDING_BACKEND", "openai"),
        description="Embedding backend: 'openai' (default), 'local' (sentence-transformers) or 'ollama'.",
    )
    ollama_embed_model: str = Field(
        default_factory=lambda: os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
        description="Ollama embedding model name (e.g. nomic-embed-text).",
    )
    gemini_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY"),
        description="API key for Google Gemini (env: GEMINI_API_KEY).",
    )
    gemini_model: str = Field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        description="Gemini model name (e.g. gemini-2.5-flash).",
    )
    use_rag: bool = Field(
        default_factory=lambda: os.getenv("USE_RAG", "true").lower() != "false",
        description="Whether to query Qdrant and use external knowledge (RAG).",
    )


class LLMSeoIssue(BaseModel):
    category: str
    title: str
    impact: str
    difficulty: Optional[str] = None
    recommended_actions: List[str] = Field(default_factory=list)


class LLMSeoResponse(BaseModel):
    """
    Structured, LLM-generated SEO explanation that the frontend can render.
    """

    summary: str
    priority_issues: List[LLMSeoIssue] = Field(default_factory=list)
    quick_wins: List[str] = Field(default_factory=list)
    long_term_ideas: List[str] = Field(default_factory=list)
    # Optional AI-adjusted overall score/grade (0–100 and a short label)
    score: Optional[int] = None
    grade: Optional[str] = None


class ChatMessage(BaseModel):
    role: str
    content: str


def _build_rag_config(overrides: Optional[Dict[str, Any]] = None) -> RAGConfig:
    """
    Build a RAGConfig from environment variables plus optional overrides.

    This lets us control llm_provider / embedding_backend per request (via
    frontend settings) while still defaulting to env vars.
    """
    data: Dict[str, Any] = {
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
    }
    if overrides:
        data.update({k: v for k, v in overrides.items() if v is not None})
    return RAGConfig(**data)


def _build_case_summary(result: Dict[str, Any]) -> str:
    """
    Turn the existing analyzer JSON into a compact natural-language summary
    that can be fed into embeddings + the LLM.
    """
    http = result.get("http") or {}
    html = result.get("html") or {}
    performance = result.get("performance") or {}
    links = result.get("links") or {}

    parts = [
        f"Final URL: {result.get('final_url')}",
        f"HTTP status: {http.get('status_code')}",
        f"Response time (s): {http.get('response_time_seconds')}",
        f"HTML bytes: {http.get('content_length_bytes')}",
        f"Title length: {(html.get('title') or {}).get('length')}",
        f"Meta description length: {(html.get('meta_description') or {}).get('length')}",
        f"H1 count: {(html.get('h1') or {}).get('count')}",
        f"Word count: {html.get('word_count')}",
        f"Images total: {(html.get('images') or {}).get('total')}, without alt: {(html.get('images') or {}).get('without_alt_count')}",
        f"Internal links: {links.get('internal_count')}, external links: {links.get('external_count')}",
        f"Viewport present: {(html.get('viewport_present'))}",
        f"Structured data present: {html.get('structured_data_present')}",
        f"Open Graph present: {html.get('open_graph_present')}, Twitter Card present: {html.get('twitter_card_present')}",
    ]

    recs_by_cat = result.get("recommendations_by_category") or {}
    total_recs = sum(len(v or []) for v in recs_by_cat.values())
    parts.append(f"Total heuristic recommendations: {total_recs}")

    return "\n".join(str(p) for p in parts if p is not None)


def _get_openai_client(cfg: RAGConfig, *, require: bool) -> Optional[OpenAI]:
    """
    Return an OpenAI client when OpenAI is actually needed, otherwise None.

    - For structured analysis (/api/analyze_llm) we set require=True and always
      expect a working OpenAI configuration.
    - For chat with a local LLM + local embeddings, require=False so we don't
      force an OpenAI key.
    """
    # If neither chat nor embeddings use OpenAI, we don't need a client.
    if cfg.llm_provider != "openai" and cfg.embedding_backend != "openai":
        if require:
            raise RAGConfigError(
                "OpenAI client requested but llm_provider/embedding_backend are not 'openai'."
            )
        return None

    try:
        # The OpenAI client also reads OPENAI_API_KEY / OPENAI_BASE_URL from env;
        # we still validate that an API key is present for clearer errors.
        if not cfg.openai_api_key:
            raise RAGConfigError("OPENAI_API_KEY is not set; cannot run OpenAI-based analysis.")
        os.environ.setdefault("OPENAI_API_KEY", cfg.openai_api_key)
        return OpenAI()
    except Exception as exc:
        raise RAGConfigError(f"Failed to initialise OpenAI client: {exc}") from exc


def _get_qdrant_client(cfg: RAGConfig) -> Optional[QdrantClient]:
    if not cfg.qdrant_url:
        print("[RAG] QDRANT_URL not set; skipping RAG retrieval")
        return None
    try:
        client = QdrantClient(url=cfg.qdrant_url, api_key=cfg.qdrant_api_key)
        # Light-touch connectivity check: list collections to ensure the URL/API key work.
        client.get_collections()
        return client
    except Exception as exc:
        # Retrieval is optional; if Qdrant is misconfigured we simply skip it,
        # but we log the reason so it's debuggable.
        print(f"[RAG] Failed to initialise Qdrant client for {cfg.qdrant_url}: {exc}")
        return None


def _retrieve_knowledge_passages(
    cfg: RAGConfig, client: Optional[OpenAI], case_summary: str
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Retrieve SEO knowledge passages from the vector DB relevant to this case.

    If Qdrant is not configured, this gracefully returns an empty list so that
    the LLM can still operate, just with less external context.
    """
    if not cfg.use_rag:
        print("[RAG] use_rag is False; skipping retrieval")
        return [], []

    qdrant = _get_qdrant_client(cfg)
    if qdrant is None:
        print("[RAG] Qdrant client is not available; skipping retrieval")
        return [], []

    # Embed the query via one of the configured backends.
    if cfg.embedding_backend == "local":
        try:
            model_name = os.getenv("LOCAL_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
            st_model = SentenceTransformer(model_name)
            vector = st_model.encode([case_summary], normalize_embeddings=True)[0].tolist()
        except Exception as exc:
            print(f"[RAG] Local embedding backend failed: {exc}")
            return [], []
    elif cfg.embedding_backend == "ollama":
        try:
            vector = ollama_embed(cfg.ollama_embed_model, case_summary)
        except OllamaError as exc:
            print(f"[RAG] Ollama embedding backend failed: {exc}")
            return [], []
        except Exception as exc:
            print(f"[RAG] Ollama embedding backend unexpected error: {exc}")
            return [], []
    else:
        if client is None:
            # OpenAI embeddings requested but no client available.
            print("[RAG] OpenAI embedding backend requested but no OpenAI client available")
            return [], []
        try:
            emb_resp = client.embeddings.create(
                model=cfg.embedding_model,
                input=case_summary,
            )
            vector = emb_resp.data[0].embedding
        except Exception as exc:
            # If embeddings fail, fall back to no retrieval.
            print(f"[RAG] OpenAI embeddings failed: {exc}")
            return [], []

    try:
        # qdrant-client API has evolved; support multiple variants:
        # - Older: QdrantClient.search(..., query_vector=..., query_filter=...)
        # - Newer: QdrantClient.search_points(..., query_vector=..., query_filter=...)
        # - Newest: QdrantClient.query_points(..., query=..., filter=...)
        if hasattr(qdrant, "search_points"):
            search_result = qdrant.search_points(
                collection_name=cfg.qdrant_collection,
                query_vector=vector,
                limit=cfg.max_passages,
                with_payload=True,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="type",
                            match=MatchValue(value="seo_guide"),
                        )
                    ]
                ),
            )
        elif hasattr(qdrant, "query_points"):
            # Some qdrant-client versions use `query_filter` here as well.
            search_result = qdrant.query_points(
                collection_name=cfg.qdrant_collection,
                query=vector,
                limit=cfg.max_passages,
                with_payload=True,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="type",
                            match=MatchValue(value="seo_guide"),
                        )
                    ]
                ),
            )
        elif hasattr(qdrant, "search"):
            search_result = qdrant.search(
                collection_name=cfg.qdrant_collection,
                query_vector=vector,
                limit=cfg.max_passages,
                with_payload=True,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="type",
                            match=MatchValue(value="seo_guide"),
                        )
                    ]
                ),
            )
        else:
            print("[RAG] Qdrant client has no supported search method (search_points/query_points/search)")
            return [], []
    except Exception as exc:
        print(f"[RAG] Qdrant search failed: {exc}")
        return [], []

    passages: List[str] = []
    sources: List[Dict[str, Any]] = []

    def _extract_payload_and_score(point: Any) -> Tuple[Dict[str, Any], Optional[float]]:
        """Handle different qdrant-client return types (ScoredPoint, dict, tuples)."""
        payload: Dict[str, Any] = {}
        score_val: Optional[float] = None

        # Newer clients: ScoredPoint with .payload / .score
        if hasattr(point, "payload"):
            payload = getattr(point, "payload") or {}
            score_val = getattr(point, "score", None)
            return payload, score_val

        # Sometimes results may be plain dicts
        if isinstance(point, dict):
            payload = (point.get("payload") or point) or {}
            score_val = point.get("score")
            return payload, score_val

        # Some client paths may return tuples/lists; search for a dict or object with .payload
        if isinstance(point, (list, tuple)):
            for item in point:
                if hasattr(item, "payload"):
                    payload = getattr(item, "payload") or {}
                    score_val = getattr(item, "score", None)
                    return payload, score_val
                if isinstance(item, dict):
                    payload = (item.get("payload") or item) or {}
                    score_val = item.get("score")
                    return payload, score_val

        return payload, score_val

    if search_result:
        try:
            print(f"[RAG] Retrieved {len(search_result)} passages from '{cfg.qdrant_collection}'")
            for point in search_result:
                payload, _score = _extract_payload_and_score(point)
                print(
                    "[RAG] hit source:",
                    payload.get("source_url"),
                    "topic:",
                    payload.get("topic"),
                    "doc_type:",
                    payload.get("doc_type"),
                )
        except Exception:
            # Logging should never break retrieval.
            pass

    for point in search_result:
        payload, score_val = _extract_payload_and_score(point)
        text = payload.get("text") or payload.get("content")
        if isinstance(text, str):
            passages.append(text)
        sources.append(
            {
                "source_url": payload.get("source_url"),
                "topic": payload.get("topic"),
                "doc_type": payload.get("doc_type"),
                "score": score_val,
            }
        )
    return passages, sources


def _build_llm_prompt(
    result: Dict[str, Any],
    case_summary: str,
    knowledge_passages: List[str],
) -> str:
    """
    Build a single user-facing prompt string that contains:
    - a short description of the situation
    - the raw analyzer JSON
    - retrieved knowledge chunks
    """
    blocks: List[str] = []

    blocks.append("You are an experienced SEO consultant.")
    blocks.append(
        "You receive structured analysis data about a single URL, plus optional reference material "
        "from SEO best-practices documents. Use ONLY this information to give practical, honest advice."
    )

    blocks.append("\n[CASE SUMMARY]")
    blocks.append(case_summary)

    blocks.append("\n[ANALYZER_JSON]")
    blocks.append(json.dumps(result, ensure_ascii=False))

    if knowledge_passages:
        blocks.append("\n[REFERENCE_SEO_MATERIAL]")
        for idx, passage in enumerate(knowledge_passages, start=1):
            blocks.append(f"--- SOURCE {idx} ---")
            blocks.append(passage)

    blocks.append(
        "\n[INSTRUCTIONS]\n"
        "1. Prioritise issues that have the highest likely impact on organic search visibility and clicks.\n"
        "2. Do not invent metrics (like Core Web Vitals) that are not present in the data.\n"
        "3. When something is unknown, say it is unknown and base advice on general best practices.\n"
        "4. Tailor recommendations and EXAMPLES to this specific page (its URL, language, content and issues), "
        "not generic SEO theory.\n"
        "5. For each priority issue, provide at least two concrete, context-aware recommended_actions, such as "
        "sample titles, meta descriptions, heading text, or structured data snippets that would make sense for "
        "this site.\n"
        "6. Suggest an overall SEO score (0–100) and grade name based on impact and severity of issues.\n"
        "7. Respond STRICTLY in the JSON schema described below, without additional commentary.\n\n"
        "JSON schema:\n"
        "{\n"
        '  "summary": "Short paragraph (2–4 sentences) explaining the overall SEO situation for this URL.",\n'
        '  "priority_issues": [\n'
        "    {\n"
        '      "category": "title | meta_description | content | technical | performance | mobile | structured_data | links | images | social | internationalization | canonical | off_page",\n'
        '      "title": "Short title for this issue (max 80 chars)",\n'
        '      "impact": "high | medium | low",\n'
        '      "difficulty": "easy | moderate | hard",\n'
        '      "recommended_actions": ["Concrete, context-aware step 1 with example tailored to this URL", "Step 2", "..."]\n'
        "    }\n"
        "  ],\n"
        '  "quick_wins": ["Concrete actions that can realistically be done within a day."],\n'
        '  "long_term_ideas": ["Bigger projects or strategic ideas that require more effort."],\n'
        '  "score": 0,  // integer 0–100, where higher is better; you may reuse the heuristic score when reasonable\n'
        '  "grade": "Excellent | Good | Needs improvement | Critical"  // or a close variant\n'
        "}\n"
    )

    return "\n".join(blocks)


def generate_llm_analysis(result: Dict[str, Any], overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Main entry point used by FastAPI.

    Takes the existing analyzer JSON and returns a structured, LLM-generated
    explanation + plan that the frontend can render.
    """
    cfg = _build_rag_config(overrides)
    # For analysis we support both OpenAI and Ollama. We still allow OpenAI-based
    # embeddings if requested via EMBEDDING_BACKEND.
    client = _get_openai_client(cfg, require=cfg.llm_provider == "openai" or cfg.embedding_backend == "openai")

    case_summary = _build_case_summary(result)
    knowledge_passages, rag_sources = _retrieve_knowledge_passages(cfg, client, case_summary)
    prompt = _build_llm_prompt(result, case_summary, knowledge_passages)

    if cfg.llm_provider == "ollama":
        # Ask Ollama to follow the same JSON schema as OpenAI; we validate after.
        try:
            content = ollama_chat(
                cfg.local_llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert, senior-level SEO consultant. "
                            "You explain clearly, avoid fluff, and focus on concrete actions. "
                            "Respond STRICTLY as valid JSON following the schema described in the user message. "
                            "Do not include any extra commentary outside the JSON."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.3,
            )
        except OllamaError as exc:
            raise RAGConfigError(str(exc)) from exc
        except Exception as exc:
            raise RAGConfigError(f"Ollama chat call failed: {exc}") from exc
    elif cfg.llm_provider == "gemini":
        try:
            content = gemini_chat(
                cfg.gemini_model,
                prompt=(
                    "You are an expert, senior-level SEO consultant. "
                    "You explain clearly, avoid fluff, and focus on concrete actions. "
                    "Respond STRICTLY as valid JSON following the schema described in the prompt below. "
                    "Do not include any extra commentary outside the JSON.\n\n"
                    + prompt
                ),
                api_key=cfg.gemini_api_key or "",
                temperature=0.3,
            )
        except GeminiError as exc:
            raise RAGConfigError(str(exc)) from exc
        except Exception as exc:
            raise RAGConfigError(f"Gemini call failed: {exc}") from exc
    else:
        try:
            completion = client.chat.completions.create(
                model=cfg.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert, senior-level SEO consultant. "
                            "You explain clearly, avoid fluff, and focus on concrete actions."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )
        except Exception as exc:
            raise RAGConfigError(f"OpenAI chat.completions call failed: {exc}") from exc

        content = completion.choices[0].message.content or "{}"

    # Gemini and other providers might occasionally wrap JSON in code fences or text.
    def _extract_json_block(text: str) -> str:
        stripped = (text or "").strip()
        # Remove Markdown-style ```json ``` fences if present.
        if stripped.startswith("```"):
            # drop first fence line
            lines = stripped.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            # drop closing fence if present
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            stripped = "\n".join(lines).strip()
        # Heuristic: take substring from first '{' to last '}' if present.
        if "{" in stripped and "}" in stripped:
            start = stripped.find("{")
            end = stripped.rfind("}") + 1
            candidate = stripped[start:end].strip()
            if candidate:
                return candidate
        return stripped

    try:
        parsed = LLMSeoResponse.model_validate_json(content)
    except ValidationError:
        # If the model returns something slightly off-schema, try to coerce to JSON
        # (e.g. strip code fences / leading commentary) and then re-validate.
        coerced = _extract_json_block(content)
        try:
            data = json.loads(coerced)
        except Exception:
            # As a final fallback, try parsing as a Python literal (tolerates single quotes, etc.).
            try:
                data = ast.literal_eval(coerced)
                parsed = LLMSeoResponse.model_validate(data)
            except Exception as exc:  # pragma: no cover - very defensive path
                # If we still can't parse, don't fail the whole request; instead,
                # wrap the raw text in a minimal LLMSeoResponse so the UI can
                # still display something useful.
                print(f"[RAG] Failed to parse LLM JSON response, falling back to raw text: {exc}")
                parsed = LLMSeoResponse(
                    summary=coerced[:2000] if coerced else (content or "")[:2000],
                    priority_issues=[],
                    quick_wins=[],
                    long_term_ideas=[],
                    score=None,
                    grade=None,
                )
        else:
            # json.loads path succeeded
            parsed = LLMSeoResponse.model_validate(data)

    result_payload = parsed.model_dump()
    # Attach debug info about which RAG sources were used (if any).
    result_payload["rag_sources"] = rag_sources
    return result_payload


def chat_about_analysis(
    result: Dict[str, Any],
    messages: List[Dict[str, str]],
    overrides: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Lightweight chat helper: answer follow-up questions about a single analyzed URL.

    The frontend sends the current analyzer JSON plus a short chat history; we
    build a focused prompt that reuses the same RAG knowledge base.
    """
    if not messages:
        raise RAGConfigError("No chat messages provided.")

    cfg = _build_rag_config(overrides)
    # For chat we may or may not need OpenAI depending on configuration.
    client = _get_openai_client(cfg, require=False)

    case_summary = _build_case_summary(result)

    # Use the last user message as the retrieval query focus.
    last_user = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user = msg.get("content", "").strip()
            break

    retrieval_query = case_summary
    if last_user:
        retrieval_query += "\n\nUser question:\n" + last_user

    knowledge_passages, _ = _retrieve_knowledge_passages(cfg, client, retrieval_query)

    context_blocks: List[str] = []
    context_blocks.append("[ANALYZER SUMMARY]\n" + case_summary)
    if knowledge_passages:
        context_blocks.append("\n[REFERENCE SEO MATERIAL]")
        for idx, p in enumerate(knowledge_passages, start=1):
            context_blocks.append(f"--- SOURCE {idx} ---\n{p}")
    context_text = "\n".join(context_blocks)

    system_message = (
        "You are an experienced SEO consultant. A separate analyzer has already inspected a "
        "specific URL and produced structured data; you also have access to some SEO "
        "best-practice reference material.\n\n"
        "Use ONLY the provided analysis and reference material when answering. "
        "Explain clearly, avoid fluff, and focus on concrete, practical advice. "
        "If something is unknown, say so honestly.\n\n"
        "Format your responses for readability:\n"
        "- Use short sections with brief headings (e.g. 'Title & meta', 'Content', 'Technical').\n"
        "- Use numbered lists for step-by-step actions.\n"
        "- Use bullet points for options or examples.\n"
        "- Add blank lines between sections so the text is easy to scan."
    )

    # We keep the user's chat history, but prepend a single assistant message that
    # injects the analysis context so each reply is grounded.
    history: List[Dict[str, str]] = [{"role": "system", "content": system_message}]
    history.append(
        {
            "role": "assistant",
            "content": (
                "Here is the SEO analysis summary and reference material for the current page:\n\n"
                f"{context_text}"
            ),
        }
    )
    history.extend(ChatMessage(**m).model_dump() for m in messages)

    if cfg.llm_provider == "ollama":
        try:
            return ollama_chat(cfg.local_llm_model, history, temperature=0.4)
        except OllamaError as exc:
            raise RAGConfigError(str(exc)) from exc
        except Exception as exc:
            raise RAGConfigError(f"Ollama chat call failed: {exc}") from exc
    elif cfg.llm_provider == "gemini":
        # Flatten the history into a single prompt string for Gemini.
        convo_lines: List[str] = []
        for msg in history:
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")
            if not content:
                continue
            convo_lines.append(f"{role}: {content}")
        flat_prompt = "\n\n".join(convo_lines)

        try:
            return gemini_chat(
                cfg.gemini_model,
                prompt=flat_prompt,
                api_key=cfg.gemini_api_key or "",
                temperature=0.4,
            )
        except GeminiError as exc:
            raise RAGConfigError(str(exc)) from exc
        except Exception as exc:
            raise RAGConfigError(f"Gemini call failed: {exc}") from exc
    else:
        try:
            completion = client.chat.completions.create(
                model=cfg.openai_model,
                messages=history,
                temperature=0.4,
            )
        except Exception as exc:
            raise RAGConfigError(f"OpenAI chat.completions call failed: {exc}") from exc

        content = completion.choices[0].message.content or ""
        return content



from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, List
from urllib.parse import urlparse
import os

from .seo_analyzer import analyze_url, normalize_url
from .rag_service import RAGConfigError, chat_about_analysis, generate_llm_analysis


class AnalyzeRequest(BaseModel):
    url: str


class AnalyzeLLMRequest(AnalyzeRequest):
    """
    LLM-enhanced analysis request.

    - provider: optional override for LLM provider ('openai' or 'ollama')
    - embedding_backend: optional override for embedding backend
      ('openai', 'local', or 'ollama')
    """

    provider: str | None = None
    embedding_backend: str | None = None
    use_rag: bool | None = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    # The analyzer result JSON from /api/analyze or /api/analyze_llm
    analysis: Dict[str, Any]
    # Optional LLM summary object returned from /api/analyze_llm (not required,
    # but included so we can refine prompts later if needed).
    llm: Dict[str, Any] | None = None
    messages: List[ChatMessage]
    # Optional overrides for provider / embedding backend, same semantics as
    # AnalyzeLLMRequest.
    provider: str | None = None
    embedding_backend: str | None = None
    use_rag: bool | None = None


app = FastAPI(title="SEO Analyzer API", version="0.1.0")

allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()] or [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {"status": "ok"}


def _normalize_and_validate_url(raw_url: str) -> str:
    raw = (raw_url or "").strip()
    target = normalize_url(raw)
    parsed = urlparse(target)

    if not parsed.scheme:
        raise HTTPException(
            status_code=422,
            detail="URL must start with http:// or https:// (e.g. https://example.com).",
        )
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(
            status_code=422,
            detail="Only http:// and https:// URLs are supported.",
        )
    if not parsed.netloc:
        raise HTTPException(
            status_code=422,
            detail="URL must contain a domain name (e.g. example.com).",
        )
    if not parsed.hostname or "." not in parsed.hostname:
        raise HTTPException(
            status_code=422,
            detail="The domain name looks invalid. Make sure it includes a dot, e.g. example.com.",
        )

    return target


@app.post("/api/analyze")
def analyze(request: AnalyzeRequest) -> Dict[str, Any]:
    target_url = _normalize_and_validate_url(request.url)

    try:
        result = analyze_url(target_url)
        return {"ok": True, "data": result}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")


@app.post("/api/analyze_llm")
def analyze_llm(request: AnalyzeLLMRequest) -> Dict[str, Any]:
    """
    Run the existing heuristic analyzer and then enrich the result with
    LLM / RAG-based recommendations.
    """
    target_url = _normalize_and_validate_url(request.url)

    try:
        base_result = analyze_url(target_url)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")

    try:
        overrides = {
            "llm_provider": request.provider,
            "embedding_backend": request.embedding_backend,
            "use_rag": request.use_rag,
        }
        llm_payload = generate_llm_analysis(base_result, overrides=overrides)
    except RAGConfigError as cfg_exc:
        # Configuration/connection issues: surface a clear error but keep the
        # base analyzer result so the endpoint is still useful.
        raise HTTPException(
            status_code=500,
            detail=str(cfg_exc),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM analysis failed: {exc}")

    return {
        "ok": True,
        "data": base_result,
        "llm": llm_payload,
    }


@app.post("/api/chat_llm")
def chat_llm(request: ChatRequest) -> Dict[str, Any]:
    """
    Chat endpoint to ask follow-up questions about a single analyzed URL.

    The frontend sends the analyzer JSON (and optionally the LLM summary)
    plus a short chat history. We answer based on that context + RAG.
    """
    if not request.messages:
        raise HTTPException(status_code=422, detail="messages must not be empty")

    try:
        overrides = {
            "llm_provider": request.provider,
            "embedding_backend": request.embedding_backend,
            "use_rag": request.use_rag,
        }
        reply = chat_about_analysis(
            request.analysis,
            [m.model_dump() for m in request.messages],
            overrides=overrides,
        )
    except RAGConfigError as cfg_exc:
        raise HTTPException(status_code=500, detail=str(cfg_exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat failed: {exc}")

    return {"ok": True, "message": reply}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)

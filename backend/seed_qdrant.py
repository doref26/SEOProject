import json
import os
from pathlib import Path
from typing import List, Tuple
from uuid import uuid4

from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PayloadSchemaType, PointStruct, VectorParams


QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION = os.getenv("QDRANT_COLLECTION", "seo_knowledge")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBED_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_FILE = BASE_DIR / "seo_knowledge.json"


def load_documents() -> List[Tuple[str, dict]]:
    """
    Load knowledge items to be inserted into Qdrant.

    - If backend/seo_knowledge.json exists, each entry should look like:
        {
          "id": "optional-stable-id",
          "url": "https://example.com/some-guide",
          "title": "Descriptive title",
          "text": "Longer explanation / notes..."
        }
      The text we embed will be: "Title: ...\\nURL: ...\\n\\n{text}"

    - If the file does not exist, we fall back to a few built-in example docs.
    """
    if KNOWLEDGE_FILE.exists():
        print(f"Loading knowledge items from {KNOWLEDGE_FILE} ...")
        raw = json.loads(KNOWLEDGE_FILE.read_text(encoding="utf-8"))
        docs: List[Tuple[str, dict]] = []
        for item in raw:
            url = (item.get("source_url") or item.get("url") or "").strip()
            title = (item.get("title") or url or "SEO guide").strip()
            text_body = (item.get("text") or item.get("content") or "").strip()
            if not text_body:
                continue
            full_text = f"Title: {title}\n"
            if url:
                full_text += f"URL: {url}\n\n"
            full_text += text_body
            # Start with all user-provided metadata (engine, topic, doc_type, version_date, lang, etc.)
            payload = dict(item)
            # Normalise a few common fields and ensure type/text/full_text are set.
            payload.update(
                {
                    "text": text_body,
                    "full_text": full_text,
                    "title": title,
                    "url": url or None,
                    "type": payload.get("type", "seo_guide"),
                    "source_url": url or payload.get("source_url"),
                }
            )
            docs.append((full_text, payload))
        if docs:
            return docs
        print("seo_knowledge.json was found but contained no usable items; using defaults.")

    # Fallback: a few built-in example documents.
    print("seo_knowledge.json not found; seeding with built-in example SEO tips.")
    examples = [
        "Title tags should usually be 50–60 characters and include the main keyword near the start.",
        "Meta descriptions should summarize the page in 120–155 characters and encourage clicks.",
        "Use a single H1 per page that describes the main topic, with supporting H2/H3 headings.",
    ]
    return [(text, {"text": text, "type": "seo_guide"}) for text in examples]


def main() -> None:
    if not QDRANT_URL or not QDRANT_API_KEY:
        raise RuntimeError("QDRANT_URL and QDRANT_API_KEY must be set in the environment.")

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    print(f"Recreating collection '{COLLECTION}' (size=1536, distance=cosine)...")
    client.recreate_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
    )
    # Create payload indexes for common filter fields (improves filtered search performance).
    indexed_fields = {
        "engine": PayloadSchemaType.KEYWORD,
        "topic": PayloadSchemaType.KEYWORD,
        "doc_type": PayloadSchemaType.KEYWORD,
        "lang": PayloadSchemaType.KEYWORD,
        "version_date": PayloadSchemaType.KEYWORD,
        "type": PayloadSchemaType.KEYWORD,
    }
    for field_name, schema_type in indexed_fields.items():
        try:
            client.create_payload_index(
                collection_name=COLLECTION,
                field_name=field_name,
                field_schema=schema_type,
            )
            print(f"Created payload index on field '{field_name}'")
        except Exception as exc:
            print(f"Warning: could not create index for '{field_name}': {exc}")

    if not OPENAI_API_KEY:
        # Allow running this script without embeddings so that the collection and
        # indexes are created. Actual document insertion will require embeddings.
        print(
            "OPENAI_API_KEY is not set; created collection and payload indexes only. "
            "No documents were embedded or inserted."
        )
        return

    oai = OpenAI(api_key=OPENAI_API_KEY)

    docs = load_documents()
    texts = [t for t, _ in docs]

    print(f"Creating embeddings for {len(texts)} documents using {EMBED_MODEL} ...")
    emb_resp = oai.embeddings.create(model=EMBED_MODEL, input=texts)

    points = []
    for (text, payload), emb in zip(docs, emb_resp.data):
        points.append(
            PointStruct(
                id=str(uuid4()),
                vector=emb.embedding,
                payload=payload,
            )
        )

    client.upsert(collection_name=COLLECTION, points=points)
    print(f"Seeded Qdrant collection '{COLLECTION}' with {len(points)} documents.")


if __name__ == "__main__":
    main()
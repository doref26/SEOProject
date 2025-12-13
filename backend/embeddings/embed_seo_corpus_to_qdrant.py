import json
import os
from pathlib import Path
from typing import Dict, List

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PayloadSchemaType, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from backend.llm_providers.ollama_client import OllamaError, ollama_embed


BASE_DIR = Path(__file__).resolve().parent
CORPUS_FILE = BASE_DIR / "seo_corpus.jsonl"

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION = os.getenv("QDRANT_COLLECTION", "seo_knowledge")

EMBEDDING_BACKEND = os.getenv("EMBEDDING_BACKEND", "local")  # 'local' or 'ollama'
LOCAL_EMBED_MODEL = os.getenv(
    "LOCAL_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")


def _require_env() -> None:
    if not QDRANT_URL or not QDRANT_API_KEY:
        raise RuntimeError("QDRANT_URL and QDRANT_API_KEY must be set in the environment.")
    if not CORPUS_FILE.exists():
        raise RuntimeError(f"Corpus file not found: {CORPUS_FILE}")


def _embed_batch_texts(texts: List[str]) -> List[List[float]]:
    """
    Embed a batch of texts using the configured backend.
    For local backend we embed in a real batch; for Ollama we call per text.
    """
    if EMBEDDING_BACKEND == "ollama":
        vecs: List[List[float]] = []
        for t in texts:
            try:
                vec = ollama_embed(OLLAMA_EMBED_MODEL, t)
                vecs.append(vec)
            except OllamaError as exc:
                raise RuntimeError(f"Ollama embedding failed: {exc}") from exc
        return vecs

    # Default: local sentence-transformers
    try:
        model = SentenceTransformer(LOCAL_EMBED_MODEL)
        arr = model.encode(texts, normalize_embeddings=True)
        return [list(map(float, v)) for v in arr]
    except Exception as exc:
        raise RuntimeError(f"Local embedding model failed: {exc}") from exc


def main() -> None:
    """
    Read seo_corpus.jsonl, embed each chunk, and upsert into Qdrant's seo_knowledge
    collection with payload that matches this project's RAG expectations.
    """
    _require_env()

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    # Peek at first record to determine vector size
    with CORPUS_FILE.open("r", encoding="utf-8") as f:
        first_line = f.readline()
        if not first_line:
            raise RuntimeError("seo_corpus.jsonl is empty.")
        first_rec: Dict = json.loads(first_line)
        test_vec = _embed_batch_texts([first_rec["text"]])[0]
        vector_size = len(test_vec)

    print(f"Recreating collection '{COLLECTION}' with vector size {vector_size} ...")
    client.recreate_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )

    # Create payload indexes for common filters
    indexed_fields = {
        "engine": PayloadSchemaType.KEYWORD,
        "topic": PayloadSchemaType.KEYWORD,
        "doc_type": PayloadSchemaType.KEYWORD,
        "lang": PayloadSchemaType.KEYWORD,
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

    # Now embed and upsert all records (including the first one we peeked)
    def iter_records():
        with CORPUS_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                yield json.loads(line)

    batch: List[PointStruct] = []
    batch_texts: List[str] = []
    batch_recs: List[Dict] = []
    batch_size = 32

    for rec in iter_records():
        batch_recs.append(rec)
        batch_texts.append(rec["text"])

        if len(batch_texts) >= batch_size:
            vecs = _embed_batch_texts(batch_texts)
            for rec_item, vec in zip(batch_recs, vecs):
                payload = {
                    "source_url": rec_item["url"],
                    "source_domain": rec_item.get("source_domain"),
                    "title": rec_item.get("title"),
                    "section_path": rec_item.get("section_path") or [],
                    "text": rec_item["text"],
                    "engine": rec_item.get("engine"),
                    "topic": rec_item.get("topic"),
                    "doc_type": rec_item.get("doc_type"),
                    "lang": rec_item.get("lang"),
                    "version_date": rec_item.get("version_date"),
                    "crawled_at": rec_item.get("crawled_at"),
                    "chunk_index": rec_item.get("chunk_index"),
                    "chunk_char_start": rec_item.get("chunk_char_start"),
                    "chunk_char_end": rec_item.get("chunk_char_end"),
                    # This 'type' field is used by the RAG filter in rag_service.py
                    "type": "seo_guide",
                }
                batch.append(
                    PointStruct(
                        id=rec_item.get("id"),
                        vector=vec,
                        payload=payload,
                    )
                )

            client.upsert(collection_name=COLLECTION, points=batch)
            print(f"Upserted batch of {len(batch)} points.")
            batch = []
            batch_texts = []
            batch_recs = []

    # Final partial batch
    if batch_texts:
        vecs = _embed_batch_texts(batch_texts)
        for rec_item, vec in zip(batch_recs, vecs):
            payload = {
                "source_url": rec_item["url"],
                "source_domain": rec_item.get("source_domain"),
                "title": rec_item.get("title"),
                "section_path": rec_item.get("section_path") or [],
                "text": rec_item["text"],
                "engine": rec_item.get("engine"),
                "topic": rec_item.get("topic"),
                "doc_type": rec_item.get("doc_type"),
                "lang": rec_item.get("lang"),
                "version_date": rec_item.get("version_date"),
                "crawled_at": rec_item.get("crawled_at"),
                "chunk_index": rec_item.get("chunk_index"),
                "chunk_char_start": rec_item.get("chunk_char_start"),
                "chunk_char_end": rec_item.get("chunk_char_end"),
                "type": "seo_guide",
            }
            batch.append(
                PointStruct(
                    id=rec_item.get("id"),
                    vector=vec,
                    payload=payload,
                )
            )

        client.upsert(collection_name=COLLECTION, points=batch)
        print(f"Upserted final batch of {len(batch)} points.")

    print(f"Finished embedding and upserting corpus into collection '{COLLECTION}'.")


if __name__ == "__main__":
    main()



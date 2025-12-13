import os
from typing import Dict, List
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)
from sentence_transformers import SentenceTransformer


QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION = os.getenv("QDRANT_COLLECTION", "seo_knowledge")

# Sentence-transformers model; all-MiniLM-L6-v2 produces 384-dim embeddings
LOCAL_EMBED_MODEL = os.getenv(
    "LOCAL_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
VECTOR_SIZE = 384


def _require_env() -> None:
    if not QDRANT_URL or not QDRANT_API_KEY:
        raise RuntimeError("QDRANT_URL and QDRANT_API_KEY must be set in the environment.")


def _get_docs() -> List[Dict]:
    """
    Base SEO corpus based on the plan we designed earlier.

    This is a compact, manually curated set of docs; you can extend it or
    replace it with loading from a JSON file if you prefer.
    """
    return [
        # 1. Core Google search rules
        {
            "id": "google-search-essentials",
            "source_url": "https://developers.google.com/search/docs/essentials",
            "title": "Google Search Essentials",
            "text": "Google's main rulebook for sites to appear in Search: technical requirements, spam policies, and basic SEO best practices.",
            "engine": "google",
            "topic": "google_core",
            "doc_type": "guideline",
            "lang": "en",
        },
        {
            "id": "google-spam-policies",
            "source_url": "https://developers.google.com/search/docs/essentials/spam-policies",
            "title": "Spam Policies for Google Web Search",
            "text": "Official list of spam practices that can lead to demotion or removal from Google Search, including cloaking, link schemes, and auto-generated content.",
            "engine": "google",
            "topic": "google_core",
            "doc_type": "guideline",
            "lang": "en",
        },
        # 2. Crawling & indexing: sitemaps, robots.txt (sample)
        {
            "id": "sitemaps-protocol-spec",
            "source_url": "https://www.sitemaps.org/protocol.html",
            "title": "Sitemaps protocol specification",
            "text": "Canonical XML Sitemaps specification defining sitemap formats, limits, and examples.",
            "engine": "generic",
            "topic": "crawling_indexing",
            "doc_type": "spec",
            "lang": "en",
        },
        {
            "id": "google-build-sitemap",
            "source_url": "https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap",
            "title": "Build and submit a sitemap",
            "text": "Google-specific guidance for creating and submitting XML sitemaps, including size limits and best practices.",
            "engine": "google",
            "topic": "crawling_indexing",
            "doc_type": "guideline",
            "lang": "en",
        },
        # 3. Structured data & schema (sample)
        {
            "id": "google-structured-data-intro",
            "source_url": "https://developers.google.com/search/docs/appearance/structured-data/intro-structured-data",
            "title": "Intro to structured data",
            "text": "Google documentation explaining what structured data is, supported formats, and how search features use it.",
            "engine": "google",
            "topic": "structured_data",
            "doc_type": "guideline",
            "lang": "en",
        },
        {
            "id": "schema-org-docs",
            "source_url": "https://schema.org/docs/documents.html",
            "title": "Schema.org documentation hub",
            "text": "Overview of schema.org documentation, including type definitions, examples, and developer guides.",
            "engine": "generic",
            "topic": "schema_vocabulary",
            "doc_type": "vocabulary",
            "lang": "en",
        },
        # 4. Page experience & Core Web Vitals (sample)
        {
            "id": "google-core-web-vitals",
            "source_url": "https://developers.google.com/search/docs/appearance/core-web-vitals",
            "title": "Core Web Vitals and Google Search",
            "text": "Explains how Core Web Vitals metrics like LCP, CLS, and INP relate to user experience and Google rankings.",
            "engine": "google",
            "topic": "page_experience",
            "doc_type": "guideline",
            "lang": "en",
        },
        # 5. Social metadata (sample)
        {
            "id": "open-graph-spec",
            "source_url": "https://ogp.me/",
            "title": "Open Graph protocol specification",
            "text": "Defines Open Graph meta tags (og:title, og:description, og:image, etc.) for rich link previews on social platforms.",
            "engine": "generic",
            "topic": "social_metadata",
            "doc_type": "spec",
            "lang": "en",
        },
    ]


def main() -> None:
    """
    Create the `seo_knowledge` collection (or recreate it) and upload a small,
    curated SEO corpus using a local embedding model (no external embedding API).
    """
    _require_env()

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    print(f"Recreating collection '{COLLECTION}' (size={VECTOR_SIZE}, distance=cosine)...")
    client.recreate_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )

    # Payload indexes for common filters
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

    print(f"Loading local embedding model '{LOCAL_EMBED_MODEL}' ...")
    model = SentenceTransformer(LOCAL_EMBED_MODEL)

    docs = _get_docs()
    texts = [f"Title: {d['title']}\nURL: {d['source_url']}\n\n{d['text']}" for d in docs]

    print(f"Encoding {len(texts)} documents with the local model ...")
    vectors = model.encode(texts, normalize_embeddings=True)

    points: List[PointStruct] = []
    for doc, vec, full_text in zip(docs, vectors, texts):
        payload = {
            "doc_id": doc.get("id"),
            "source_url": doc["source_url"],
            "title": doc["title"],
            "text": doc["text"],
            "full_text": full_text,
            "engine": doc["engine"],
            "topic": doc["topic"],
            "doc_type": doc["doc_type"],
            "lang": doc.get("lang", "en"),
            "type": "seo_guide",
        }
        points.append(
            PointStruct(
                # Qdrant expects an unsigned int or UUID for the point ID.
                # We keep the human-readable ID in payload["doc_id"] instead.
                id=str(uuid4()),
                vector=list(map(float, vec)),
                payload=payload,
            )
        )

    client.upsert(collection_name=COLLECTION, points=points)
    print(f"Uploaded {len(points)} SEO knowledge documents to collection '{COLLECTION}'.")


if __name__ == "__main__":
    main()



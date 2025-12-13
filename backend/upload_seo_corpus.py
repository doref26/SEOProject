import os
from uuid import uuid4

from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct


QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION = os.getenv("QDRANT_COLLECTION", "seo_knowledge")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBED_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


def _require_env() -> None:
    if not QDRANT_URL or not QDRANT_API_KEY:
        raise RuntimeError("QDRANT_URL and QDRANT_API_KEY must be set in the environment.")
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY must be set in the environment to create embeddings for the SEO corpus."
        )


def _get_docs() -> list[dict]:
  """
  Base SEO corpus based on your earlier plan.

  Each entry is a high-level summary of a key document, with metadata so RAG can filter
  by engine/topic/doc_type.
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
    {
      "id": "google-helpful-content",
      "source_url": "https://developers.google.com/search/docs/fundamentals/creating-helpful-content",
      "title": "Creating helpful, reliable, people-first content",
      "text": "Guidance on writing people-first content that demonstrates experience, expertise, authoritativeness, and trustworthiness (E-E-A-T).",
      "engine": "google",
      "topic": "google_core",
      "doc_type": "guideline",
      "lang": "en",
    },
    {
      "id": "google-seo-starter-guide",
      "source_url": "https://developers.google.com/search/docs/fundamentals/seo-starter-guide",
      "title": "Google SEO Starter Guide",
      "text": "Introductory guide covering on-page SEO basics: titles, meta descriptions, headings, internal links, sitemaps, and mobile-friendly design.",
      "engine": "google",
      "topic": "google_core",
      "doc_type": "guideline",
      "lang": "en",
    },
    {
      "id": "google-get-started-developers",
      "source_url": "https://developers.google.com/search/docs/fundamentals/get-started-developers",
      "title": "Get started with Search: a developer’s guide",
      "text": "Technical overview for developers on how Google discovers, crawls, and indexes pages, and how to build search-friendly sites.",
      "engine": "google",
      "topic": "google_core",
      "doc_type": "guideline",
      "lang": "en",
    },
    # 2. Quality Rater Guidelines & E-E-A-T
    {
      "id": "google-rater-guidelines-main",
      "source_url": "https://guidelines.raterhub.com/searchqualityevaluatorguidelines.pdf",
      "title": "Search Quality Rater Guidelines",
      "text": "Detailed instructions for quality raters about Page Quality, Needs Met, E-E-A-T, and YMYL, with many real-world examples.",
      "engine": "google",
      "topic": "quality_rater",
      "doc_type": "guideline",
      "lang": "en",
    },
    {
      "id": "google-rater-overview",
      "source_url": "https://services.google.com/fh/files/misc/hsw-sqrg.pdf",
      "title": "Search Quality Rater Guidelines overview",
      "text": "Short overview version of the Search Quality Rater Guidelines, summarizing how raters assess quality and relevance.",
      "engine": "google",
      "topic": "quality_rater",
      "doc_type": "guideline",
      "lang": "en",
    },
    {
      "id": "google-e-e-a-t-blog",
      "source_url": "https://developers.google.com/search/blog/2022/12/google-raters-guidelines-e-e-a-t",
      "title": "E-E-A-T update blog post",
      "text": "Explains the introduction of Experience to E-A-T and how Google thinks about trust and quality in content.",
      "engine": "google",
      "topic": "quality_rater",
      "doc_type": "guideline",
      "lang": "en",
    },
    # 3. Crawling & indexing: sitemaps, robots.txt
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
      "id": "sitemaps-faq",
      "source_url": "https://www.sitemaps.org/faq.html",
      "title": "Sitemaps FAQ",
      "text": "Frequently asked questions about XML Sitemaps, including multiple sitemaps, index files, and update frequency.",
      "engine": "generic",
      "topic": "crawling_indexing",
      "doc_type": "guideline",
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
    {
      "id": "google-robots-intro",
      "source_url": "https://developers.google.com/search/docs/crawling-indexing/robots/intro",
      "title": "Introduction to robots.txt",
      "text": "Explains how Googlebot interprets robots.txt, including allow/disallow rules and precedence.",
      "engine": "google",
      "topic": "crawling_indexing",
      "doc_type": "guideline",
      "lang": "en",
    },
    {
      "id": "google-robots-spec",
      "source_url": "https://developers.google.com/crawling/docs/robots-txt/robots-txt-spec",
      "title": "How Google interprets the robots.txt specification",
      "text": "Details on robots.txt size limits, crawl-delay handling, sitemaps directives, wildcards, and other edge cases.",
      "engine": "google",
      "topic": "crawling_indexing",
      "doc_type": "spec",
      "lang": "en",
    },
    {
      "id": "robots-exclusion-wikipedia",
      "source_url": "https://en.wikipedia.org/wiki/Robots.txt",
      "title": "Robots Exclusion Protocol background",
      "text": "Background on the robots exclusion protocol, including historical context and basic rules.",
      "engine": "generic",
      "topic": "crawling_indexing",
      "doc_type": "guideline",
      "lang": "en",
    },
    # 4. Structured data & schema
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
      "id": "google-search-gallery",
      "source_url": "https://developers.google.com/search/docs/appearance/structured-data/search-gallery",
      "title": "Search Gallery: supported rich results",
      "text": "Gallery of all rich result types Google supports, with links to implementation details and required schema.org markup.",
      "engine": "google",
      "topic": "structured_data",
      "doc_type": "guideline",
      "lang": "en",
    },
    {
      "id": "google-org-structured-data",
      "source_url": "https://developers.google.com/search/docs/appearance/structured-data/organization",
      "title": "Organization structured data",
      "text": "Guidance on adding Organization markup, including name, logo, URL, sameAs, and contact information.",
      "engine": "google",
      "topic": "structured_data",
      "doc_type": "guideline",
      "lang": "en",
    },
    {
      "id": "google-product-structured-data",
      "source_url": "https://developers.google.com/search/docs/appearance/structured-data/product",
      "title": "Product structured data",
      "text": "Implementation details for Product rich results, including required and recommended properties for ecommerce pages.",
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
    {
      "id": "schema-org-full-hierarchy",
      "source_url": "https://schema.org/docs/full.html",
      "title": "Schema.org full type hierarchy",
      "text": "Complete list of schema.org types and their relationships, useful for understanding which properties belong to which type.",
      "engine": "generic",
      "topic": "schema_vocabulary",
      "doc_type": "vocabulary",
      "lang": "en",
    },
    # 5. Page experience & Core Web Vitals
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
    {
      "id": "google-page-experience",
      "source_url": "https://developers.google.com/search/docs/appearance/page-experience",
      "title": "Understanding page experience in Google Search",
      "text": "Describes page experience as a ranking signal, including mobile friendliness, HTTPS, intrusive interstitials, and Core Web Vitals.",
      "engine": "google",
      "topic": "page_experience",
      "doc_type": "guideline",
      "lang": "en",
    },
    {
      "id": "web-dev-core-web-vitals",
      "source_url": "https://web.dev/explore/learn-core-web-vitals",
      "title": "Learn Core Web Vitals (web.dev)",
      "text": "Deep, technical guidance on measuring and improving Core Web Vitals metrics, with examples and tooling tips.",
      "engine": "generic",
      "topic": "page_experience",
      "doc_type": "guideline",
      "lang": "en",
    },
    # 6. Bing / Microsoft
    {
      "id": "bing-webmaster-guidelines",
      "source_url": "https://www.bing.com/webmasters/help/webmaster-guidelines-30fba23a",
      "title": "Bing Webmaster Guidelines",
      "text": "Bing's official guidance on how it discovers, crawls, indexes, and ranks content in Microsoft Bing.",
      "engine": "bing",
      "topic": "bing_core",
      "doc_type": "guideline",
      "lang": "en",
    },
    {
      "id": "bing-webmaster-support",
      "source_url": "https://www.bing.com/webmasters/help/webmaster-support-24ab5ebf",
      "title": "Bing Webmaster support hub",
      "text": "Support resources and troubleshooting docs for Bing Webmaster Tools, crawling issues, and indexing problems.",
      "engine": "bing",
      "topic": "bing_core",
      "doc_type": "guideline",
      "lang": "en",
    },
    # 7. Social preview & meta protocols
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
    {
      "id": "facebook-sharing-webmasters",
      "source_url": "https://developers.facebook.com/docs/sharing/webmasters/",
      "title": "Facebook Sharing / Webmasters docs",
      "text": "Guidance for how Facebook uses Open Graph tags to generate link previews and how to debug sharing issues.",
      "engine": "generic",
      "topic": "social_metadata",
      "doc_type": "guideline",
      "lang": "en",
    },
    {
      "id": "twitter-cards-markup",
      "source_url": "https://developer.x.com/en/docs/x-for-websites/cards/overview/markup",
      "title": "Twitter/X Cards markup reference",
      "text": "Reference for Twitter/X Cards meta tags, including card types, required properties, and examples.",
      "engine": "generic",
      "topic": "social_metadata",
      "doc_type": "spec",
      "lang": "en",
    },
    # 8. Curated checklists & learning maps
    {
      "id": "github-renuo-seo-checklist",
      "source_url": "https://github.com/renuo/seo-checklist",
      "title": "Renuo SEO Checklist",
      "text": "Community-maintained SEO checklist covering technical, on-page, and off-page optimization tasks.",
      "engine": "generic",
      "topic": "seo_checklists",
      "doc_type": "checklist",
      "lang": "en",
    },
    {
      "id": "github-flowforfrank-seo-checklist",
      "source_url": "https://github.com/flowforfrank/seo-checklist",
      "title": "FlowForFrank SEO Checklist",
      "text": "Detailed SEO requirements and best practices checklist for different aspects of a website.",
      "engine": "generic",
      "topic": "seo_checklists",
      "doc_type": "checklist",
      "lang": "en",
    },
    {
      "id": "learningseo-roadmap",
      "source_url": "https://learningseo.io/",
      "title": "LearningSEO.io roadmap",
      "text": "Curated roadmap of SEO learning resources, organized by topics like technical SEO, content, and analytics.",
      "engine": "generic",
      "topic": "seo_checklists",
      "doc_type": "guideline",
      "lang": "en",
    },
  ]


def main() -> None:
    _require_env()

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    oai = OpenAI(api_key=OPENAI_API_KEY)

    docs = _get_docs()
    texts = [f"Title: {d['title']}\nURL: {d['source_url']}\n\n{d['text']}" for d in docs]

    print(f"Creating embeddings for {len(texts)} SEO corpus entries using {EMBED_MODEL} ...")
    emb_resp = oai.embeddings.create(model=EMBED_MODEL, input=texts)

    points: list[PointStruct] = []
    for doc, emb in zip(docs, emb_resp.data):
        payload = {
            "source_url": doc["source_url"],
            "title": doc["title"],
            "text": doc["text"],
            "full_text": texts[docs.index(doc)],
            "engine": doc["engine"],
            "topic": doc["topic"],
            "doc_type": doc["doc_type"],
            "lang": doc.get("lang", "en"),
            "type": "seo_guide",
        }
        points.append(
            PointStruct(
                id=doc.get("id") or str(uuid4()),
                vector=emb.embedding,
                payload=payload,
            )
        )

    client.upsert(collection_name=COLLECTION, points=points)
    print(f"Uploaded {len(points)} SEO knowledge documents to collection '{COLLECTION}'.")


if __name__ == "__main__":
  main()



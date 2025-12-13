import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse
from uuid import uuid4

import requests
from bs4 import BeautifulSoup


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = BASE_DIR / "seo_corpus.jsonl"

DEFAULT_HEADERS = {
    # Pretend to be a regular browser so some sites (e.g. Wikipedia) are less
    # likely to block the request. This is still subject to their robots.txt / TOS.
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# 1) List the main SEO docs you want to include in the corpus.
#    You can extend this list as needed.
URLS: List[str] = [
    # Google core / guidelines
    "https://developers.google.com/search/docs/essentials",
    "https://developers.google.com/search/docs/essentials/spam-policies",
    "https://developers.google.com/search/docs/fundamentals/seo-starter-guide",
    "https://developers.google.com/search/docs/fundamentals/creating-helpful-content",
    "https://developers.google.com/search/docs/fundamentals/get-started-developers",
    # Crawling & indexing
    "https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap",
    "https://developers.google.com/search/docs/crawling-indexing/robots/intro",
    "https://developers.google.com/crawling/docs/robots-txt/robots-txt-spec",
    # Structured data & schema
    "https://developers.google.com/search/docs/appearance/structured-data/intro-structured-data",
    "https://developers.google.com/search/docs/appearance/structured-data/search-gallery",
    "https://developers.google.com/search/docs/appearance/structured-data/organization",
    "https://developers.google.com/search/docs/appearance/structured-data/product",
    "https://schema.org/docs/documents.html",
    "https://schema.org/docs/full.html",
    # Page experience & Core Web Vitals
    "https://developers.google.com/search/docs/appearance/page-experience",
    "https://developers.google.com/search/docs/appearance/core-web-vitals",
    "https://web.dev/explore/learn-core-web-vitals",
    # Sitemaps / robots / protocols
    "https://www.sitemaps.org/protocol.html",
    "https://www.sitemaps.org/faq.html",
    "https://en.wikipedia.org/wiki/Robots.txt",
    # Social metadata: Open Graph, Twitter/X Cards
    "https://ogp.me/",
    "https://developers.facebook.com/docs/sharing/webmasters/",
    "https://developer.x.com/en/docs/x-for-websites/cards/overview/markup",
    # Bing guidelines
    "https://www.bing.com/webmasters/help/webmaster-guidelines-30fba23a",
    "https://developers.google.com/search/docs/fundamentals/creating-helpful-content",
    "https://developers.google.com/search/docs/appearance/ranking-systems-guide",
    "https://developers.google.com/search/docs/fundamentals/how-search-works",
    "https://developers.google.com/search/docs/crawling-indexing",
    "https://support.google.com/websearch/answer/10622781?hl=en",
    "https://developers.google.com/search/docs/monitor-debug/search-console-start",
    "https://search.google.com/search-console/about",
    "https://developers.google.com/search/docs/appearance/structured-data",
    "https://developers.google.com/search/docs/appearance/structured-data/organization",
    "https://developers.google.com/search/blog/2022/11/introducing-guide-to-ranking-systems",
    "https://blog.google/products/search/google-search-update-march-2024/",
    "https://yandex.com/support/webmaster/en/",
    "https://webmaster.yandex.com/site/optimization/seo-guide/",
    "https://www.bing.com/webmasters/help/refreshed-webmaster-tools-7c7d2533",
    "https://schema.org/docs/developers.html",
    "https://schema.org/docs/gs.html",
    "https://schema.org/docs/schemas.html",
    "https://schema.org/docs/datamodel.html",
    "https://moz.com/beginners-guide-to-seo",
    "https://moz.com/learn/seo",
    "https://ahrefs.com/seo",
    "https://ahrefs.com/academy/seo-training-course",
    "https://learningseo.io/",
    # Bad SEO practices / spam / penalties
    "https://support.google.com/webmasters/answer/9044175?hl=en",
    "https://developers.google.com/search/docs/essentials/spam-policies",
    "https://developers.google.com/search/blog/2014/04/webmaster-guidelines-for-sneaky",
    "https://digitalmarketinginstitute.com/blog/the-ultimate-guide-to-bad-seo-practices",
    "https://searchengineland.com/guide/seo/violations-search-engine-spam-penalties",
    "https://www.seocasestudy.com/seo-examples/black-hat-seo",
    "https://www.digitalauthority.me/resources/black-hat-seo-practices/",
    "https://hawthorncreative.com/blog/why-you-should-steer-clear-of-these-black-hat-seo-tactics-and-what-to-do-instead/",
    "https://www.bluehost.com/blog/black-hat-seo-techniques/",
    "https://www.creaitor.ai/blog/black-hat-seo-guide",
    "https://rankmath.com/seo-glossary/link-scheme/",
    "https://bluetree.digital/google-backlink-policy/",
    "https://backlinkmanager.io/blog/navigating-google-penalties-quick-guide/",
    "https://www.rhinorank.io/blog/identify-and-avoid-spam-links/",
    "https://www.goodsignals.com/seo/google-guidelines/",
    "https://zeo.org/resources/blog/the-complete-list-of-google-penalties-manual-actions-guide",
    "https://brandwell.ai/blog/what-is-cloaking-in-seo/",
    "https://eseospace.com/how-to-avoid-google-penalties/",
    "https://www.ladybugz.com/bad-seo-practices-and-seo-mistakes-you-want-to-avoid/",
]


def infer_metadata(url: str) -> Dict[str, str]:
    """
    Infer engine/topic/doc_type metadata based on the URL.

    This mapping is tailored to this project's topics:
      - google_core
      - crawling_indexing
      - structured_data
      - schema_vocabulary
      - page_experience
      - bing_core
      - social_metadata
      - bad_practices
      - seo_education
      - other_engines
    """
    parsed = urlparse(url)
    domain = parsed.netloc
    path = parsed.path

    meta: Dict[str, str] = {
        "source_domain": domain,
        "engine": "generic",
        "topic": "generic",
        "doc_type": "guideline",
        "lang": "en",
    }

    if "developers.google.com" in domain:
        meta["engine"] = "google"
        # Spam / sneaky redirects focused docs
        if "spam-policies" in path or "/search/blog/2014/04/webmaster-guidelines-for-sneaky" in path:
            meta["topic"] = "bad_practices"
        elif "/search/docs/essentials" in path or "/fundamentals" in path:
            meta["topic"] = "google_core"
        elif "/search/docs/crawling-indexing" in path:
            meta["topic"] = "crawling_indexing"
        elif "/search/docs/appearance/structured-data" in path:
            meta["topic"] = "structured_data"
        elif "/search/docs/appearance/core-web-vitals" in path or "/page-experience" in path:
            meta["topic"] = "page_experience"
        else:
            meta["topic"] = "google_core"

    # Google blog posts about ranking systems / updates
    elif "blog.google" in domain:
        meta["engine"] = "google"
        meta["topic"] = "google_core"

    # Search Console / about Search
    elif "search.google.com" in domain:
        meta["engine"] = "google"
        meta["topic"] = "google_core"

    elif "support.google.com" in domain:
        meta["engine"] = "google"
        # Manual actions / penalties (webmasters section)
        if "/webmasters/" in path:
            meta["topic"] = "bad_practices"
        else:
            meta["topic"] = "google_core"

    elif "schema.org" in domain:
        meta["topic"] = "schema_vocabulary"
        meta["doc_type"] = "vocabulary"

    elif "sitemaps.org" in domain:
        meta["topic"] = "crawling_indexing"
        meta["doc_type"] = "spec"

    # Robots.txt reference
    elif "wikipedia.org" in domain and "Robots.txt" in path:
        meta["topic"] = "crawling_indexing"
        meta["doc_type"] = "spec"

    elif "ogp.me" in domain:
        meta["topic"] = "social_metadata"
        meta["doc_type"] = "spec"

    elif "developers.facebook.com" in domain:
        meta["topic"] = "social_metadata"
        meta["doc_type"] = "guideline"

    elif "developer.x.com" in domain or "dev.twitter.com" in domain:
        meta["topic"] = "social_metadata"
        meta["doc_type"] = "guideline"

    # Core Web Vitals / web.dev
    elif "web.dev" in domain:
        meta["topic"] = "page_experience"
        meta["doc_type"] = "guideline"

    elif "bing.com" in domain:
        meta["engine"] = "bing"
        meta["topic"] = "bing_core"

    # Yandex webmaster docs
    elif "yandex.com" in domain or "yandex.ru" in domain or "webmaster.yandex.com" in domain:
        meta["engine"] = "yandex"
        meta["topic"] = "other_engines"

    # General SEO education / guides
    elif domain in (
        "moz.com",
        "ahrefs.com",
        "learningseo.io",
    ):
        meta["topic"] = "seo_education"
        meta["doc_type"] = "guideline"

    # Generic "bad SEO practices" / spammy tactics and penalty deep-dives
    elif domain in (
        "digitalmarketinginstitute.com",
        "searchengineland.com",
        "www.seocasestudy.com",
        "www.digitalauthority.me",
        "hawthorncreative.com",
        "www.bluehost.com",
        "www.creaitor.ai",
        "rankmath.com",
        "bluetree.digital",
        "backlinkmanager.io",
        "www.rhinorank.io",
        "www.goodsignals.com",
        "zeo.org",
        "brandwell.ai",
        "eseospace.com",
        "www.ladybugz.com",
    ):
        meta["topic"] = "bad_practices"
        meta["doc_type"] = "guideline"

    return meta


def extract_main_text(html: str) -> str:
    """
    Very simple text extractor: strips script/style/nav/footer and keeps visible text.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove script/style/noscript
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # Remove obvious nav/footer/header/aside if they exist
    for tag in soup.find_all(["nav", "footer", "header", "aside"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def chunk_text(text: str, max_chars: int = 2000) -> List[str]:
    """
    Split text into reasonably sized chunks (by characters).
    """
    paragraphs = text.split("\n")
    chunks: List[str] = []
    current = ""

    for p in paragraphs:
        if not current:
            current = p
        elif len(current) + len(p) + 1 <= max_chars:
            current += "\n" + p
        else:
            chunks.append(current)
            current = p
    if current:
        chunks.append(current)

    return chunks


def build_corpus() -> None:
    """
    Crawl the configured URLs, extract main text, chunk it, and write
    a canonical JSONL corpus file (seo_corpus.jsonl) that other scripts
    can embed and upsert into Qdrant.
    """
    now_iso = datetime.utcnow().isoformat() + "Z"
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as f_out:
        for url in URLS:
            print("Fetching:", url)
            try:
                resp = requests.get(url, timeout=30, headers=DEFAULT_HEADERS)
                resp.raise_for_status()
            except requests.HTTPError as exc:
                print(f"  ! Skipping {url} due to HTTP error: {exc}")
                continue
            except requests.RequestException as exc:
                print(f"  ! Skipping {url} due to network error: {exc}")
                continue

            html = resp.text
            text = extract_main_text(html)
            chunks = chunk_text(text, max_chars=2000)

            meta = infer_metadata(url)
            # Page title
            title = url
            soup = BeautifulSoup(html, "html.parser")
            if soup.title and soup.title.string:
                title = soup.title.string.strip()

            char_index = 0
            for i, chunk in enumerate(chunks):
                start = char_index
                end = start + len(chunk)
                char_index = end + 1

                record = {
                    "id": str(uuid4()),
                    "url": url,
                    "source_domain": meta["source_domain"],
                    "title": title,
                    # Can later be filled with heading hierarchy if desired.
                    "section_path": [],
                    "text": chunk,
                    "engine": meta["engine"],
                    "topic": meta["topic"],
                    "doc_type": meta["doc_type"],
                    "lang": meta["lang"],
                    "version_date": None,  # could be parsed from visible "updated on" strings
                    "crawled_at": now_iso,
                    "chunk_index": i,
                    "chunk_char_start": start,
                    "chunk_char_end": end,
                }

                f_out.write(json.dumps(record, ensure_ascii=False) + "\n")

    print("Written JSONL corpus:", OUTPUT_FILE)


if __name__ == "__main__":
    build_corpus()



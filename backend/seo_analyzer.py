from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
import tldextract
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT_SECONDS = 15


def normalize_url(url: str) -> str:
    url = url.strip()
    # Be forgiving about accidental leading characters like '@'
    # (e.g. when pasting URLs such as '@https://example.com')
    url = re.sub(r"^@+", "", url)
    if not url:
        return url
    if not re.match(r"^https?://", url, flags=re.I):
        url = "https://" + url
    return url


def _add_recommendation(
    result: Dict[str, Any],
    *,
    category: str,
    message: str,
    purpose: str,
) -> None:
    """
    Add a recommendation in both a flat list (for backwards compatibility)
    and a structured, category-based collection for advanced SEO analysis.
    """
    # Flat list for existing consumers
    result.setdefault("recommendations", []).append(message)

    # Structured recommendations grouped by category
    cat_map = result.setdefault("recommendations_by_category", {})
    bucket = cat_map.setdefault(category, [])
    bucket.append(
        {
            "category": category,
            "message": message,
            "purpose": purpose,
        }
    )


def _fetch(url: str) -> Tuple[requests.Response, float]:
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    start = time.perf_counter()
    resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS, allow_redirects=True)
    elapsed = time.perf_counter() - start
    return resp, elapsed


def _get_base(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _is_internal(link_url: str, base_url: str) -> bool:
    try:
        link_host = urlparse(link_url).netloc
        base_host = urlparse(base_url).netloc
        if not link_host or not base_host:
            return True
        link_dom = tldextract.extract(link_host)
        base_dom = tldextract.extract(base_host)
        return (link_dom.domain, link_dom.suffix) == (base_dom.domain, base_dom.suffix)
    except Exception:
        return False


def _extract_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _fetch_robots(base_url: str) -> Dict[str, Any]:
    robots_url = urljoin(base_url, "/robots.txt")
    try:
        resp = requests.get(robots_url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT_SECONDS)
        content = resp.text if resp.status_code == 200 else ""
        lines = content.splitlines()
        group_all = []
        sitemaps: List[str] = []
        current_is_all = False
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.lower().startswith("user-agent:"):
                agent = stripped.split(":", 1)[1].strip()
                current_is_all = agent == "*" or agent == '"*"'
            elif stripped.lower().startswith("sitemap:"):
                sm = stripped.split(":", 1)[1].strip()
                sitemaps.append(sm)
            elif current_is_all:
                if any(stripped.lower().startswith(p) for p in ["allow:", "disallow:"]):
                    group_all.append(stripped)
        return {
            "url": robots_url,
            "status": resp.status_code,
            "has_robots": resp.status_code == 200,
            "rules_for_all": group_all[:50],
            "sitemaps": sitemaps[:20],
        }
    except Exception:
        return {
            "url": robots_url,
            "status": None,
            "has_robots": False,
            "rules_for_all": [],
            "sitemaps": [],
        }


def _check_sitemap(base_url: str, robots_info: Dict[str, Any]) -> Dict[str, Any]:
    candidate_urls = list(robots_info.get("sitemaps") or [])
    candidate_urls.append(urljoin(base_url, "/sitemap.xml"))
    for sm_url in candidate_urls[:5]:
        try:
            resp = requests.head(sm_url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT_SECONDS, allow_redirects=True)
            if resp.status_code == 200:
                return {"found": True, "url": sm_url, "status": 200}
        except Exception:
            continue
    return {"found": False, "url": None, "status": None}


def analyze_url(url: str) -> Dict[str, Any]:
    response, elapsed = _fetch(url)
    final_url = str(response.url)
    base_url = _get_base(final_url)

    result: Dict[str, Any] = {
        "requested_url": url,
        "final_url": final_url,
        "http": {
            "status_code": response.status_code,
            "response_time_seconds": round(elapsed, 3),
            "content_length_bytes": int(response.headers.get("Content-Length") or len(response.content or b"")),
            "server": response.headers.get("Server"),
            "content_type": response.headers.get("Content-Type"),
        },
        "html": {},
        "links": {},
        "robots": {},
        "sitemap": {},
        "recommendations": [],  # flat list of messages (backwards compatible)
        "recommendations_by_category": {},  # structured advanced analysis
    }

    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type and not (response.text or "").strip().startswith("<!DOCTYPE html"):
        result["recommendations"].append("The URL does not appear to return HTML content.")
        return result

    html = response.text or ""
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.title.string.strip() if soup.title and soup.title.string else ""
    meta_desc = ""
    for m in soup.find_all("meta"):
        name = (m.get("name") or m.get("property") or "").lower()
        if name == "description":
            meta_desc = (m.get("content") or "").strip()
            break

    canonical = None
    can_tag = soup.find("link", rel=lambda v: v and "canonical" in v.lower())
    if can_tag:
        canonical_href = can_tag.get("href")
        if canonical_href:
            canonical = urljoin(final_url, canonical_href)

    h1_tags = [h.get_text(strip=True) for h in soup.find_all("h1")]
    lang = (soup.html.get("lang") if soup.html else None) or ""

    images = soup.find_all("img")
    images_without_alt = [img.get("src") for img in images if not (img.get("alt") or "").strip()]
    images_without_alt = [urljoin(final_url, s) for s in images_without_alt if s]

    # Basic Open Graph and Twitter Card
    og_title = soup.find("meta", property="og:title")
    og_desc = soup.find("meta", property="og:description")
    tw_title = soup.find("meta", attrs={"name": "twitter:title"})
    tw_desc = soup.find("meta", attrs={"name": "twitter:description"})

    all_anchors = soup.find_all("a")
    internal_links: List[str] = []
    external_links: List[str] = []
    for a in all_anchors:
        href = a.get("href")
        if not href:
            continue
        abs_url = urljoin(final_url, href)
        if abs_url.startswith("mailto:") or abs_url.startswith("tel:"):
            continue
        if _is_internal(abs_url, final_url):
            internal_links.append(abs_url)
        else:
            external_links.append(abs_url)

    internal_links = list(dict.fromkeys(internal_links))[:200]
    external_links = list(dict.fromkeys(external_links))[:200]

    visible_text = _extract_text(soup)
    words = re.findall(r"\b\w+\b", visible_text)

    robots_info = _fetch_robots(base_url)
    sitemap_info = _check_sitemap(base_url, robots_info)

    result["html"] = {
        "title": {"text": title_tag, "length": len(title_tag)},
        "meta_description": {"text": meta_desc, "length": len(meta_desc), "present": bool(meta_desc)},
        "h1": {"count": len(h1_tags), "texts": h1_tags[:20]},
        "canonical": canonical,
        "lang": lang,
        "open_graph_present": bool(og_title or og_desc),
        "twitter_card_present": bool(tw_title or tw_desc),
        "word_count": len(words),
        "images": {
            "total": len(images),
            "without_alt_count": len(images_without_alt),
            "sample_without_alt": images_without_alt[:10],
        },
    }

    result["links"] = {
        "internal_count": len(internal_links),
        "external_count": len(external_links),
        "sample_internal": internal_links[:20],
        "sample_external": external_links[:20],
    }

    result["robots"] = robots_info
    result["sitemap"] = sitemap_info

    # Simple recommendations focused on key HTML SEO elements
    if not title_tag:
        _add_recommendation(
            result,
            category="title",
            message="Add a concise, descriptive <title> tag (ideally 50–60 characters, including the main keyword).",
            purpose="Improve relevance and click-through rate in search results.",
        )
    elif len(title_tag) < 30:
        _add_recommendation(
            result,
            category="title",
            message="The <title> tag is very short; consider adding more context and relevant keywords.",
            purpose="Help search engines understand the topic better and attract more qualified clicks.",
        )
    elif len(title_tag) > 65:
        _add_recommendation(
            result,
            category="title",
            message="The <title> tag may be too long; consider shortening it below ~60 characters to avoid truncation.",
            purpose="Ensure the full, most important part of the title is visible in search results.",
        )

    if not meta_desc:
        _add_recommendation(
            result,
            category="meta_description",
            message="Add a meta description (around 120–155 characters) that summarizes the page and encourages clicks.",
            purpose="Improve click-through rate by providing a compelling summary in search snippets.",
        )
    elif len(meta_desc) < 70:
        _add_recommendation(
            result,
            category="meta_description",
            message="Meta description is quite short; expand it to better describe the content and value of the page.",
            purpose="Give users more reasons to click by explaining benefits and key topics.",
        )
    elif len(meta_desc) > 180:
        _add_recommendation(
            result,
            category="meta_description",
            message="Meta description is long; it may be truncated in search results. Keep it focused and within ~155 characters.",
            purpose="Ensure the most important part of the description is visible in the search snippet.",
        )

    if len(h1_tags) == 0:
        _add_recommendation(
            result,
            category="headings",
            message="Add at least one H1 heading describing the page's main topic.",
            purpose="Clarify the primary topic of the page for both users and search engines.",
        )
    elif len(h1_tags) > 1:
        _add_recommendation(
            result,
            category="headings",
            message="Multiple H1 headings found; consider using a single primary H1.",
            purpose="Provide a clear, single main topic and avoid confusing page hierarchy.",
        )

    if result["links"]["external_count"] == 0:
        _add_recommendation(
            result,
            category="links",
            message="Consider adding relevant external references to authoritative sources.",
            purpose="Increase topical authority and provide users with high-quality supporting resources.",
        )

    if result["html"]["images"]["without_alt_count"] > 0:
        _add_recommendation(
            result,
            category="images",
            message="Add descriptive alt text to all images for accessibility and SEO.",
            purpose="Improve accessibility for assistive technologies and give search engines more context.",
        )

    if not robots_info.get("has_robots"):
        _add_recommendation(
            result,
            category="technical",
            message="Consider adding a robots.txt to control crawler access.",
            purpose="Help search engines understand which areas of the site should or should not be crawled.",
        )

    if not sitemap_info.get("found"):
        _add_recommendation(
            result,
            category="technical",
            message="Provide a sitemap.xml and reference it in robots.txt.",
            purpose="Help search engines discover and index important pages more efficiently.",
        )

    if not canonical:
        _add_recommendation(
            result,
            category="canonical",
            message="Add a canonical link tag to signal the preferred URL and avoid duplicate content issues.",
            purpose="Consolidate ranking signals and prevent duplicate content from competing in search results.",
        )

    if not lang:
        _add_recommendation(
            result,
            category="internationalization",
            message='Specify the language in the <html lang="..."> attribute so search engines understand the page language.',
            purpose="Ensure the page is targeted to the correct language audience and improves international SEO.",
        )

    # Social sharing tags (Open Graph / Twitter Card)
    if not result["html"]["open_graph_present"]:
        _add_recommendation(
            result,
            category="social",
            message="Add Open Graph meta tags (og:title, og:description, og:image) to improve how the page looks when shared.",
            purpose="Increase engagement on social platforms by showing rich, attractive link previews.",
        )

    if not result["html"]["twitter_card_present"]:
        _add_recommendation(
            result,
            category="social",
            message="Add Twitter Card meta tags (twitter:title, twitter:description, twitter:image) for better display on Twitter / X.",
            purpose="Ensure links shared on Twitter / X display with rich cards and clear context.",
        )

    return result





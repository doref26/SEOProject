import React, { useMemo, useState } from "react";

// Allow configuring the backend URL via Vite env (e.g. VITE_API_BASE_URL=https://msc-seo-analyzer.fly.dev)
// In local development you can keep using the relative path (proxy) by leaving this empty.
const API_BASE_URL =
  (typeof import.meta !== "undefined" &&
    import.meta.env &&
    (import.meta.env.VITE_API_BASE_URL || "").replace(/\/+$/, "")) ||
  "";

const CATEGORY_LABELS = {
  title: "Title tag",
  meta_description: "Meta description",
  headings: "Headings (H1)",
  content: "Content depth & quality",
  images: "Images",
  links: "Links",
  technical: "Technical SEO",
  performance: "Performance & Core Web Vitals (heuristics)",
  mobile: "Mobile friendliness",
  structured_data: "Structured data (schema.org)",
  canonical: "Canonicalization",
  internationalization: "Language / international targeting",
  social: "Social sharing (Open Graph & Twitter Cards)",
  off_page: "Off‑page authority & backlinks"
};

function IconBadge({ children, title }) {
  return (
    <span
      aria-hidden="true"
      title={title}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: 18,
        height: 18,
        borderRadius: 999,
        border: "1px solid #1f2937",
        background: "#020617",
        marginRight: 6,
        fontSize: 11,
        color: "#e5e7eb"
      }}
    >
      {children}
    </span>
  );
}

function IconOpenGraph() {
  return (
    <IconBadge title="Open Graph">
      OG
    </IconBadge>
  );
}

function IconTwitterX() {
  return (
    <IconBadge title="Twitter / X">
      X
    </IconBadge>
  );
}

function IconGoogle() {
  return (
    <IconBadge title="Google Search">
      G
    </IconBadge>
  );
}

function isLikelyUrl(value) {
  if (!value) return false;
  const hasScheme = /^https?:\/\//i.test(value);
  const candidate = hasScheme ? value : `https://${value}`;
  try {
    const u = new URL(candidate);
    return !!u.hostname && /\./.test(u.hostname);
  } catch {
    return false;
  }
}

function PrettyJSON({ data }) {
  const text = useMemo(() => JSON.stringify(data, null, 2), [data]);
  return (
    <pre
      style={{
        background: "#0b1020",
        color: "#d6e2ff",
        padding: "16px",
        borderRadius: "8px",
        overflowX: "auto",
        fontSize: "12px",
        lineHeight: "1.4",
        border: "1px solid #1b2440"
      }}
    >
      {text}
    </pre>
  );
}

function getAdvancedSeoInsights(result) {
  if (!result || !result.recommendations_by_category) return [];
  const byCategory = result.recommendations_by_category;
  return Object.entries(byCategory).map(([category, items]) => ({
    category,
    items: items || []
  }));
}

function getPositiveInsights(result) {
  if (!result) return [];
  const positives = [];
  const html = result.html || {};
  const http = result.http || {};
  const links = result.links || {};
  const robots = result.robots || {};
  const sitemap = result.sitemap || {};

  const title = html.title || {};
  if (title.text && title.length >= 30 && title.length <= 65) {
    positives.push("Title length looks good and should display well in search results.");
  }

  const meta = html.meta_description || {};
  if (meta.present && meta.length >= 80 && meta.length <= 170) {
    positives.push("Meta description is present and has a reasonable length.");
  }

  if (html.h1 && html.h1.count === 1) {
    positives.push("Exactly one H1 heading detected, which is a good practice for clear page hierarchy.");
  }

  if (html.open_graph_present) {
    positives.push("Open Graph tags are configured, so social shares should have rich previews.");
  }

  if (html.twitter_card_present) {
    positives.push("Twitter / X Card tags are present, improving how links look on Twitter / X.");
  }

  if (html.images && html.images.total > 0 && html.images.without_alt_count === 0) {
    positives.push("All detected images include alt text, which is great for accessibility and SEO.");
  }

  if (links.internal_count && links.internal_count >= 10) {
    positives.push("A healthy number of internal links helps users and crawlers discover related content.");
  }

  if (robots.has_robots) {
    positives.push("robots.txt is present, allowing you to control crawler access.");
  }

  if (sitemap.found) {
    positives.push("sitemap.xml was found, which helps search engines discover your pages.");
  }

  if (typeof http.response_time_seconds === "number" && http.response_time_seconds <= 1.0) {
    positives.push("Initial response time is fast, which is good for user experience and crawl efficiency.");
  }

  return positives;
}

function computeSeoScore(result, categoryLabels) {
  if (!result || !result.recommendations_by_category) {
    return null;
  }

  const baseScore = 100;
  const byCategory = result.recommendations_by_category;

  // Relative importance per category (higher = more impact on score)
  const weights = {
    title: 3,
    meta_description: 3,
    headings: 2,
    content: 3,
    images: 2,
    links: 2,
    technical: 4,
    performance: 4,
    mobile: 3,
    structured_data: 3,
    canonical: 3,
    internationalization: 2,
    social: 1,
    off_page: 1
  };

  const breakdown = [];
  let totalPenalty = 0;

  Object.entries(byCategory).forEach(([category, items]) => {
    const issues = items ? items.length : 0;
    if (!issues) return;
    const weight = weights[category] || 1;
    const rawPenalty = issues * weight;
    const cappedPenalty = Math.min(rawPenalty, 12); // cap per category so score stays interpretable
    totalPenalty += cappedPenalty;
    breakdown.push({
      category,
      label: categoryLabels[category] || category,
      issues,
      penalty: cappedPenalty
    });
  });

  const score = Math.max(0, baseScore - totalPenalty);

  let grade = "Critical";
  if (score >= 85) grade = "Excellent";
  else if (score >= 70) grade = "Good";
  else if (score >= 50) grade = "Needs improvement";

  // Sort breakdown by impact (largest penalty first)
  breakdown.sort((a, b) => b.penalty - a.penalty);

  return {
    score,
    grade,
    breakdown,
    baseScore,
    totalPenalty
  };
}

function getMainRecommendations(result, categoryLabels) {
  if (!result || !result.recommendations_by_category) return [];
  const byCategory = result.recommendations_by_category;

  const items = [];
  Object.entries(byCategory).forEach(([category, recs]) => {
    (recs || []).forEach((r) => {
      items.push({
        category,
        label: categoryLabels[category] || category,
        message: r.message,
        purpose: r.purpose
      });
    });
  });

  // Heuristic ordering: longer purpose / message first likely means more context; keep up to 5
  items.sort((a, b) => (b.message.length + (b.purpose || "").length) - (a.message.length + (a.purpose || "").length));

  return items.slice(0, 5);
}

function getScoreColor(score) {
  if (score >= 85) return "#22c55e"; // green
  if (score >= 70) return "#eab308"; // amber
  if (score >= 50) return "#f97316"; // orange
  return "#ef4444"; // red
}

function getHighlightInfoContent(key, result) {
  if (!key || !result) return null;
  const html = result.html || {};
  const links = result.links || {};
  const robots = result.robots || {};
  const sitemap = result.sitemap || {};

  switch (key) {
    case "title": {
      const titleText = html.title?.text || "";
      const length = html.title?.length ?? 0;
      return {
        title: "Title (HTML <title>)",
        description:
          "The <title> tag is the main headline that appears in search results and in the browser tab. It should clearly describe the page and include your main keyword.",
        importance:
          "A clear, well‑optimized title improves click‑through rate and helps search engines understand what the page is about.",
        details: [
          `Current title: ${titleText || "— (missing)"}`,
          `Length: ${length} characters (commonly ~50–60 characters is ideal).`
        ]
      };
    }
    case "meta_description": {
      const meta = html.meta_description || {};
      return {
        title: "Meta description",
        description:
          "The meta description is a short summary of the page that often appears under the title in search results.",
        importance:
          "A compelling description can significantly improve click‑through rate, even if it is not a direct ranking factor.",
        details: [
          `Present: ${meta.present ? "Yes" : "No"}`,
          `Length: ${meta.length ?? 0} characters.`,
          `Text: ${meta.text || "— (missing)"}`,
          "Aim for ~120–155 characters that explain the value of the page and include relevant phrases."
        ]
      };
    }
    case "h1": {
      const h1 = html.h1 || {};
      return {
        title: "H1 headings",
        description:
          "H1 headings act as the main on‑page title and should describe the primary topic of the page.",
        importance:
          "Clear headings help both users and search engines quickly understand the structure and main topic of the content.",
        details: [
          `H1 count: ${h1.count ?? 0}`,
          ...(Array.isArray(h1.texts) && h1.texts.length
            ? [`Sample H1 text: "${h1.texts[0]}"`]
            : ["No H1 headings were detected."])
        ]
      };
    }
    case "canonical": {
      return {
        title: "Canonical URL",
        description:
          "A canonical link tag tells search engines which URL is the preferred version when similar or duplicate content exists.",
        importance:
          "Using a canonical tag correctly helps consolidate ranking signals and avoid duplicate content issues.",
        details: [
          `Canonical value: ${html.canonical || "— (no canonical tag detected)"}`,
          "If multiple URLs can show the same content, they should point to a single canonical URL."
        ]
      };
    }
    case "lang": {
      return {
        title: "<html lang> attribute",
        description:
          "The lang attribute on the <html> tag declares the primary language of the page.",
        importance:
          "Setting the correct language helps search engines and assistive technologies serve the page to the right audience.",
        details: [
          `Current lang value: ${html.lang || "— (not set)"}`,
          "Use language codes like \"en\", \"he\", \"fr\" or locale‑specific codes such as \"en-US\" or \"he-IL\"."
        ]
      };
    }
    case "word_count": {
      const count = html.word_count ?? 0;
      return {
        title: "Word count",
        description:
          "Word count is a rough indicator of how much textual content the page provides.",
        importance:
          "Very thin pages may not fully answer users’ questions, while very long pages should be well structured for readability.",
        details: [
          `Detected word count: ${count}`,
          "Focus on covering the topic in enough depth to be useful, rather than hitting a specific number."
        ]
      };
    }
    case "images_without_alt": {
      const total = html.images?.total ?? 0;
      const withoutAlt = html.images?.without_alt_count ?? 0;
      return {
        title: "Images without alt text",
        description:
          "Alt text describes images for users who cannot see them and gives search engines additional context.",
        importance:
          "Good alt attributes improve accessibility and can help your images appear in image search.",
        details: [
          `Total images: ${total}`,
          `Images without alt: ${withoutAlt}`,
          "Add short, descriptive alt text to important images, especially those that convey information."
        ]
      };
    }
    case "open_graph": {
      return {
        title: "Open Graph tags",
        description:
          "Open Graph tags (og:title, og:description, og:image, etc.) control how your page appears when shared on social platforms.",
        importance:
          "Rich, well‑formatted previews increase clicks and engagement when users share your content.",
        details: [
          `Open Graph detected: ${html.open_graph_present ? "Yes" : "No"}`,
          "At minimum, define og:title, og:description and og:image that match the page’s main content."
        ]
      };
    }
    case "twitter_card": {
      return {
        title: "Twitter Card tags",
        description:
          "Twitter Card meta tags (twitter:title, twitter:description, twitter:image, etc.) define how your page looks on Twitter / X.",
        importance:
          "Proper cards help your links stand out in the feed and provide more context at a glance.",
        details: [
          `Twitter Card detected: ${html.twitter_card_present ? "Yes" : "No"}`,
          "Use at least a summary or summary_large_image card with title, description and image."
        ]
      };
    }
    case "internal_links": {
      const internal = links.internal_count ?? 0;
      return {
        title: "Internal links",
        description:
          "Internal links connect your pages to each other and help spread authority throughout the site.",
        importance:
          "Good internal linking improves crawlability and guides users to related, high‑value content.",
        details: [
          `Internal link count: ${internal}`,
          "Ensure important pages receive internal links with descriptive anchor text."
        ]
      };
    }
    case "external_links": {
      const external = links.external_count ?? 0;
      return {
        title: "External links",
        description:
          "External links point from your site to other domains, typically to cite sources or recommend resources.",
        importance:
          "Linking to high‑quality, relevant sites can strengthen topical relevance and improve user trust.",
        details: [
          `External link count: ${external}`,
          "Review that external links are relevant, up‑to‑date, and point to trustworthy domains."
        ]
      };
    }
    case "robots": {
      return {
        title: "robots.txt",
        description:
          "The robots.txt file tells search engine crawlers which areas of your site they can or cannot access.",
        importance:
          "A well‑configured robots.txt helps control crawling and avoid wasting crawl budget on unimportant URLs.",
        details: [
          `robots.txt detected: ${robots.has_robots ? "Yes" : "No"}`,
          robots.url ? `Checked URL: ${robots.url}` : "No robots.txt URL was successfully fetched."
        ]
      };
    }
    case "sitemap": {
      return {
        title: "sitemap.xml",
        description:
          "A sitemap.xml file lists important URLs on your site so search engines can discover them more easily.",
        importance:
          "Sitemaps are especially important for large sites or sites with complex navigation or many new pages.",
        details: [
          `Sitemap detected: ${sitemap.found ? "Yes" : "No"}`,
          sitemap.url ? `Sitemap URL: ${sitemap.url}` : "No sitemap URL was found or confirmed."
        ]
      };
    }
    default:
      return null;
  }
}

export default function App() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [analysisMode, setAnalysisMode] = useState("html"); // "html" | "json"
  const [highlightInfoKey, setHighlightInfoKey] = useState(null);
  const [showScoreDetails, setShowScoreDetails] = useState(false);

  const valid = isLikelyUrl(url);
  const advancedInsights = useMemo(() => getAdvancedSeoInsights(result), [result]);
  const positiveInsights = useMemo(() => getPositiveInsights(result), [result]);
  const hostInfo = useMemo(() => {
    if (!result) return { host: "", location: "" };
    try {
      const u = new URL(result.final_url || result.requested_url || "");
      const host = u.hostname;
      let location = "";
      if (host.endsWith(".il")) {
        location = "Israel";
      } else if (host.endsWith(".co.uk") || host.endsWith(".uk")) {
        location = "United Kingdom";
      } else if (host.endsWith(".de")) {
        location = "Germany";
      } else if (host.endsWith(".fr")) {
        location = "France";
      } else if (host.endsWith(".com")) {
        location = "Global (.com)";
      }
      return { host, location };
    } catch {
      return { host: "", location: "" };
    }
  }, [result]);
  const highlightInfo = useMemo(
    () => getHighlightInfoContent(highlightInfoKey, result),
    [highlightInfoKey, result]
  );
  const seoScore = useMemo(() => computeSeoScore(result, CATEGORY_LABELS), [result]);
  const mainRecommendations = useMemo(
    () => getMainRecommendations(result, CATEGORY_LABELS),
    [result]
  );

  async function handleAnalyze(e) {
    e.preventDefault();
    setError("");
    setResult(null);
    if (!valid) {
      setError("Please enter a valid URL (for example: example.com or https://example.com).");
      return;
    }
    // Normalize URL for the request and UI: ensure it includes a scheme
    let normalizedUrl = (url || "").trim();
    if (normalizedUrl && !/^https?:\/\//i.test(normalizedUrl)) {
      normalizedUrl = `https://${normalizedUrl}`;
      setUrl(normalizedUrl);
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: normalizedUrl })
      });
      let json = null;
      try {
        json = await response.json();
      } catch {
        // ignore JSON parse errors; we'll still try to show a generic error
      }

      if (!response.ok) {
        const detail = json?.detail || json?.message;
        let message = detail || "Analysis failed. Please try again.";

        if (response.status === 422) {
          message =
            detail ||
            "The URL looks invalid. Make sure it includes a domain name, and optionally http:// or https:// (for example: https://example.com).";
        } else if (response.status >= 500) {
          message =
            "The analyzer could not fetch or process this URL. The site might be slow, blocking requests, or temporarily unavailable.";
        }

        throw new Error(message);
      }

      if (!json || !json.ok) {
        throw new Error(json?.detail || "Analysis failed. Please try again.");
      }

      setResult(json.data);
    } catch (err) {
      setError(err.message || "Something went wrong while analyzing this URL.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "radial-gradient(circle at top, #1d2540 0, #020617 55%, #020617 100%)",
        color: "#e5e7eb",
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif',
        lineHeight: 1.6
      }}
    >
      <div style={{ maxWidth: "1040px", margin: "0 auto", padding: "32px 16px" }}>
        <header
          style={{
            marginBottom: "24px",
            display: "flex",
            flexDirection: "column",
            gap: "4px"
          }}
        >
          <h1
            style={{
              margin: 0,
              fontSize: "30px",
              fontWeight: 700,
              letterSpacing: "-0.02em"
            }}
          >
            SEO Analyzer
          </h1>
          <p
            style={{
              margin: "4px 0 0",
              color: "#9ca3af",
              maxWidth: "640px"
            }}
          >
            Enter a website URL to get a clear, prioritized SEO review of your titles, meta tags, content,
            technical setup and more.
          </p>
        </header>

        <form
          onSubmit={handleAnalyze}
          style={{
            display: "flex",
            gap: "8px",
            alignItems: "center",
            marginBottom: "12px"
          }}
        >
          <input
            type="text"
            placeholder="https://example.com"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            spellCheck="false"
            style={{
              flex: 1,
              padding: "12px 14px",
              borderRadius: "8px",
              border: "1px solid #1f2937",
              background: "#0b1224",
              color: "#e5e7eb",
              outline: "none"
            }}
          />
          <button
            type="submit"
            disabled={!valid || loading}
            style={{
              padding: "12px 16px",
              borderRadius: "8px",
              border: "none",
              background: valid && !loading ? "#2563eb" : "#1e293b",
              color: valid && !loading ? "white" : "#9ca3af",
              cursor: valid && !loading ? "pointer" : "not-allowed",
              fontWeight: 600
            }}
          >
            {loading ? "Analyzing..." : "Analyze"}
          </button>
        </form>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            marginBottom: "16px",
            fontSize: "14px"
          }}
        >
          <span style={{ color: "#94a3b8" }}>Analysis view:</span>
          <div
            style={{
              display: "inline-flex",
              padding: "2px",
              borderRadius: "999px",
              background: "#020617",
              border: "1px solid #1e293b"
            }}
          >
            <button
              type="button"
              onClick={() => setAnalysisMode("html")}
              style={{
                padding: "6px 12px",
                borderRadius: "999px",
                border: "none",
                fontSize: "13px",
                cursor: "pointer",
                background: analysisMode === "html" ? "#2563eb" : "transparent",
                color: analysisMode === "html" ? "#ffffff" : "#cbd5f5"
              }}
            >
              HTML-based
            </button>
            <button
              type="button"
              onClick={() => setAnalysisMode("json")}
              style={{
                padding: "6px 12px",
                borderRadius: "999px",
                border: "none",
                fontSize: "13px",
                cursor: "pointer",
                background: analysisMode === "json" ? "#2563eb" : "transparent",
                color: analysisMode === "json" ? "#ffffff" : "#cbd5f5"
              }}
            >
              JSON-based
            </button>
          </div>
        </div>

        {error && (
          <div
            style={{
              background: "#1f2937",
              border: "1px solid #b91c1c",
              color: "#fee2e2",
              padding: "12px 14px",
              borderRadius: "10px",
              marginBottom: "16px",
              fontSize: "13px"
            }}
          >
            {error}
          </div>
        )}

        {result && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "20px" }}>
            <section
              style={{
                background: "#0b1224",
                border: "1px solid #1b2440",
                borderRadius: "8px",
                padding: "16px"
              }}
            >
              <h2 style={{ marginTop: 0, fontSize: "18px" }}>Summary</h2>
              {seoScore && (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: 6,
                    marginBottom: 12
                  }}
                >
                  <button
                    type="button"
                    onClick={() => setShowScoreDetails(true)}
                    style={{
                      width: "80px",
                      height: "80px",
                      borderRadius: "999px",
                      border: `4px solid ${getScoreColor(seoScore.score)}`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: "22px",
                      fontWeight: 700,
                      background: "#020617",
                      color: getScoreColor(seoScore.score),
                      cursor: "pointer"
                    }}
                    title="Click to see how this SEO score was calculated"
                  >
                    {seoScore.score}
                  </button>
                  <div style={{ fontSize: "13px", color: "#cbd5f5" }}>
                    Overall SEO score: <strong>{seoScore.score}/100</strong> ({seoScore.grade})
                  </div>
                </div>
              )}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                <div><strong>Final URL:</strong> {result.final_url}</div>
                <div><strong>Status:</strong> {result.http?.status_code}</div>
                <div>
                  <strong>Response time:</strong>{" "}
                  <span
                    style={{
                      color:
                        typeof result.http?.response_time_seconds === "number"
                          ? result.http.response_time_seconds <= 1
                            ? "#22c55e"
                            : result.http.response_time_seconds <= 2
                            ? "#eab308"
                            : "#f97316"
                          : "#e5e7eb"
                    }}
                  >
                    {result.http?.response_time_seconds}s
                  </span>
                </div>
                <div><strong>Content length:</strong> {result.http?.content_length_bytes} bytes</div>
              </div>
              {seoScore && mainRecommendations.length > 0 && (
                <div style={{ marginTop: "10px" }}>
                  <h3 style={{ margin: "0 0 4px", fontSize: "14px" }}>Main SEO issues to focus on</h3>
                  <ul style={{ margin: 0, paddingLeft: "18px", fontSize: "13px", color: "#f97316" }}>
                    {mainRecommendations.slice(0, 3).map((rec, idx) => (
                      <li key={idx}>
                        <strong>{rec.label}:</strong> {rec.message}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </section>

            {analysisMode === "html" && (
              <>
            <section
              style={{
                background: "#0b1224",
                border: "1px solid #1b2440",
                borderRadius: "8px",
                padding: "16px"
              }}
            >
                  <h2 style={{ marginTop: 0, fontSize: "18px" }}>Preview: search result &amp; social card</h2>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 1fr",
                      gap: "12px"
                    }}
                  >
                    <div
                      style={{
                        borderRadius: "10px",
                        border: "1px solid #1f2937",
                        background: "#020617",
                        padding: "10px 12px",
                        minHeight: "90px"
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 6,
                          marginBottom: 4,
                          fontSize: "13px",
                          color: "#9ca3af"
                        }}
                      >
                        <IconGoogle />
                        <span>Google search preview</span>
                      </div>
                      <div style={{ fontSize: "11px", color: "#6ee7b7", marginBottom: 2 }}>
                        {hostInfo.host || "your-domain.com"}
                        {hostInfo.location && ` · ${hostInfo.location}`}
                      </div>
                      <div
                        style={{
                          fontSize: "13px",
                          fontWeight: 600,
                          color: "#e5e7eb",
                          marginBottom: 2
                        }}
                      >
                        {(() => {
                          const title = result.html?.title?.text || "No title set";
                          return title.length > 60 ? `${title.slice(0, 57)}…` : title;
                        })()}
                      </div>
                      <div style={{ fontSize: "12px", color: "#cbd5f5" }}>
                        {(() => {
                          const fallback =
                            "No meta description found. Google may pull text from the page instead.";
                          const text = result.html?.meta_description?.text || fallback;
                          return text.length > 155 ? `${text.slice(0, 152)}…` : text;
                        })()}
                      </div>
                    </div>

                    <div
                      style={{
                        borderRadius: "10px",
                        border: "1px solid #1f2937",
                        background: "#020617",
                        padding: "10px 12px",
                        minHeight: "90px",
                        display: "flex",
                        flexDirection: "column",
                        gap: 6
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 6,
                          fontSize: "13px",
                          color: "#9ca3af"
                        }}
                      >
                        <IconOpenGraph />
                        <IconTwitterX />
                        <span>Social card preview (Open Graph / Twitter)</span>
                      </div>
                      <div
                        style={{
                          display: "flex",
                          gap: 8,
                          alignItems: "stretch"
                        }}
                      >
                      {(() => {
                        const ogImg = result.html?.open_graph_image;
                        const fallbackImg =
                          result.html?.images?.sample_without_alt &&
                          result.html.images.sample_without_alt.length > 0
                            ? result.html.images.sample_without_alt[0]
                            : null;
                        const imgUrl = ogImg || fallbackImg || null;
                        return (
                        <div
                          style={{
                            width: "34%",
                            minWidth: "80px",
                            borderRadius: "6px",
                            background: imgUrl
                              ? `center/cover no-repeat url(${imgUrl})`
                              : "#111827",
                            border: "1px solid #1f2937",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: "11px",
                            color: "#e5e7eb",
                            textAlign: "center",
                            padding: "4px"
                          }}
                        >
                            {imgUrl ? "" : "No OG / social image detected"}
                        </div>
                        );
                      })()}
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div
                            style={{
                              fontSize: "13px",
                              fontWeight: 600,
                              color: "#e5e7eb",
                              marginBottom: 2
                            }}
                          >
                            {(() => {
                              const title = result.html?.title?.text || "Page title";
                              return title.length > 60 ? `${title.slice(0, 57)}…` : title;
                            })()}
                          </div>
                          <div style={{ fontSize: "12px", color: "#cbd5f5" }}>
                            {(() => {
                              const fallback = "Social networks may pull text from the page content.";
                              const text = result.html?.meta_description?.text || fallback;
                              return text.length > 110 ? `${text.slice(0, 107)}…` : text;
                            })()}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </section>

            <section
              style={{
                background: "#0b1224",
                border: "1px solid #1b2440",
                borderRadius: "8px",
                padding: "16px"
              }}
            >
                  <h2 style={{ marginTop: 0, fontSize: "18px" }}>Highlights (HTML)</h2>
                  <ul style={{ margin: 0, paddingLeft: "16px", listStyle: "none" }}>
                    <li
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: "8px",
                        marginBottom: "4px"
                      }}
                    >
                      <div>
                        <strong>Title (HTML &lt;title&gt;):</strong>{" "}
                        <span
                          style={{
                            color:
                              result.html?.title?.text && result.html.title.length >= 30 && result.html.title.length <= 65
                                ? "#e5e7eb"
                                : "#f97316"
                          }}
                        >
                          {result.html?.title?.text || "—"} ({result.html?.title?.length} chars)
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setHighlightInfoKey("title")}
                        style={{
                          width: "22px",
                          height: "22px",
                          borderRadius: "999px",
                          border: "1px solid #1f2937",
                          background: "#020617",
                          color: "#e5e7eb",
                          fontSize: "12px",
                          cursor: "pointer",
                          flexShrink: 0
                        }}
                        title="More information about the title check"
                      >
                        i
                      </button>
                    </li>
                    <li
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: "8px",
                        marginBottom: "4px"
                      }}
                    >
                      <div>
                        <strong>Meta description:</strong>{" "}
                        <span
                          style={{
                            color:
                              result.html?.meta_description?.present &&
                              result.html.meta_description.length >= 80 &&
                              result.html.meta_description.length <= 170
                                ? "#e5e7eb"
                                : "#f97316"
                          }}
                        >
                          {result.html?.meta_description?.text || "—"}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setHighlightInfoKey("meta_description")}
                        style={{
                          width: "22px",
                          height: "22px",
                          borderRadius: "999px",
                          border: "1px solid #1f2937",
                          background: "#020617",
                          color: "#e5e7eb",
                          fontSize: "12px",
                          cursor: "pointer",
                          flexShrink: 0
                        }}
                        title="More information about the meta description check"
                      >
                        i
                      </button>
                    </li>
                    <li
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: "8px",
                        marginBottom: "4px"
                      }}
                    >
                      <div>
                        <strong>H1 count:</strong>{" "}
                        <span
                          style={{
                            color:
                              result.html?.h1?.count === 1
                                ? "#e5e7eb"
                                : "#f97316"
                          }}
                        >
                          {result.html?.h1?.count}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setHighlightInfoKey("h1")}
                        style={{
                          width: "22px",
                          height: "22px",
                          borderRadius: "999px",
                          border: "1px solid #1f2937",
                          background: "#020617",
                          color: "#e5e7eb",
                          fontSize: "12px",
                          cursor: "pointer",
                          flexShrink: 0
                        }}
                        title="More information about the H1 headings check"
                      >
                        i
                      </button>
                    </li>
                    <li
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: "8px",
                        marginBottom: "4px"
                      }}
                    >
                      <div>
                        <strong>Canonical:</strong>{" "}
                        <span
                          style={{
                            color: result.html?.canonical ? "#e5e7eb" : "#f97316"
                          }}
                        >
                          {result.html?.canonical || "—"}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setHighlightInfoKey("canonical")}
                        style={{
                          width: "22px",
                          height: "22px",
                          borderRadius: "999px",
                          border: "1px solid #1f2937",
                          background: "#020617",
                          color: "#e5e7eb",
                          fontSize: "12px",
                          cursor: "pointer",
                          flexShrink: 0
                        }}
                        title="More information about the canonical URL check"
                      >
                        i
                      </button>
                    </li>
                    <li
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: "8px",
                        marginBottom: "4px"
                      }}
                    >
                      <div>
                        <strong>Language:</strong>{" "}
                        <span
                          style={{
                            color: result.html?.lang ? "#e5e7eb" : "#f97316"
                          }}
                        >
                          {result.html?.lang || "—"}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setHighlightInfoKey("lang")}
                        style={{
                          width: "22px",
                          height: "22px",
                          borderRadius: "999px",
                          border: "1px solid #1f2937",
                          background: "#020617",
                          color: "#e5e7eb",
                          fontSize: "12px",
                          cursor: "pointer",
                          flexShrink: 0
                        }}
                        title="More information about the language check"
                      >
                        i
                      </button>
                    </li>
                    <li
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: "8px",
                        marginBottom: "4px"
                      }}
                    >
                      <div>
                        <strong>Word count:</strong>{" "}
                        <span
                          style={{
                            color:
                              typeof result.html?.word_count === "number" &&
                              result.html.word_count >= 300 &&
                              result.html.word_count <= 2500
                                ? "#e5e7eb"
                                : "#f97316"
                          }}
                        >
                          {result.html?.word_count}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setHighlightInfoKey("word_count")}
                        style={{
                          width: "22px",
                          height: "22px",
                          borderRadius: "999px",
                          border: "1px solid #1f2937",
                          background: "#020617",
                          color: "#e5e7eb",
                          fontSize: "12px",
                          cursor: "pointer",
                          flexShrink: 0
                        }}
                        title="More information about the word count check"
                      >
                        i
                      </button>
                    </li>
                    <li
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: "8px",
                        marginBottom: "4px"
                      }}
                    >
                      <div>
                        <strong>Images without alt:</strong>{" "}
                        <span
                          style={{
                            color:
                              result.html?.images?.without_alt_count
                                ? "#f97316"
                                : "#e5e7eb"
                          }}
                        >
                          {result.html?.images?.without_alt_count}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setHighlightInfoKey("images_without_alt")}
                        style={{
                          width: "22px",
                          height: "22px",
                          borderRadius: "999px",
                          border: "1px solid #1f2937",
                          background: "#020617",
                          color: "#e5e7eb",
                          fontSize: "12px",
                          cursor: "pointer",
                          flexShrink: 0
                        }}
                        title="More information about the image alt text check"
                      >
                        i
                      </button>
                    </li>
                    <li
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: "8px",
                        marginBottom: "4px"
                      }}
                    >
                      <div>
                        <strong>
                          <IconOpenGraph />
                          Open Graph tags (og:*):
                        </strong>{" "}
                        <span
                          style={{
                            color: result.html?.open_graph_present ? "#e5e7eb" : "#f97316"
                          }}
                        >
                          {result.html?.open_graph_present ? "Present" : "Missing"}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setHighlightInfoKey("open_graph")}
                        style={{
                          width: "22px",
                          height: "22px",
                          borderRadius: "999px",
                          border: "1px solid #1f2937",
                          background: "#020617",
                          color: "#e5e7eb",
                          fontSize: "12px",
                          cursor: "pointer",
                          flexShrink: 0
                        }}
                        title="More information about the Open Graph check"
                      >
                        i
                      </button>
                    </li>
                    <li
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: "8px",
                        marginBottom: "4px"
                      }}
                    >
                      <div>
                        <strong>
                          <IconTwitterX />
                          Twitter / X Card tags:
                        </strong>{" "}
                        <span
                          style={{
                            color: result.html?.twitter_card_present ? "#e5e7eb" : "#f97316"
                          }}
                        >
                          {result.html?.twitter_card_present ? "Present" : "Missing"}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setHighlightInfoKey("twitter_card")}
                        style={{
                          width: "22px",
                          height: "22px",
                          borderRadius: "999px",
                          border: "1px solid #1f2937",
                          background: "#020617",
                          color: "#e5e7eb",
                          fontSize: "12px",
                          cursor: "pointer",
                          flexShrink: 0
                        }}
                        title="More information about the Twitter Card check"
                      >
                        i
                      </button>
                    </li>
                    <li
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: "8px",
                        marginBottom: "4px"
                      }}
                    >
                      <div>
                        <strong>Internal links:</strong>{" "}
                        <span
                          style={{
                            color:
                              typeof result.links?.internal_count === "number" &&
                              result.links.internal_count >= 5
                                ? "#e5e7eb"
                                : "#f97316"
                          }}
                        >
                          {result.links?.internal_count}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setHighlightInfoKey("internal_links")}
                        style={{
                          width: "22px",
                          height: "22px",
                          borderRadius: "999px",
                          border: "1px solid #1f2937",
                          background: "#020617",
                          color: "#e5e7eb",
                          fontSize: "12px",
                          cursor: "pointer",
                          flexShrink: 0
                        }}
                        title="More information about the internal links check"
                      >
                        i
                      </button>
                    </li>
                    <li
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: "8px",
                        marginBottom: "4px"
                      }}
                    >
                      <div>
                        <strong>External links:</strong>{" "}
                        <span
                          style={{
                            color:
                              typeof result.links?.external_count === "number" &&
                              result.links.external_count > 0 &&
                              result.links.external_count <= 50
                                ? "#e5e7eb"
                                : "#f97316"
                          }}
                        >
                          {result.links?.external_count}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setHighlightInfoKey("external_links")}
                        style={{
                          width: "22px",
                          height: "22px",
                          borderRadius: "999px",
                          border: "1px solid #1f2937",
                          background: "#020617",
                          color: "#e5e7eb",
                          fontSize: "12px",
                          cursor: "pointer",
                          flexShrink: 0
                        }}
                        title="More information about the external links check"
                      >
                        i
                      </button>
                    </li>
                    <li
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: "8px",
                        marginBottom: "4px"
                      }}
                    >
                      <div>
                        <strong>robots.txt:</strong>{" "}
                        <span
                          style={{
                            color: result.robots?.has_robots ? "#e5e7eb" : "#f97316"
                          }}
                        >
                          {result.robots?.has_robots ? "Present" : "Missing"}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setHighlightInfoKey("robots")}
                        style={{
                          width: "22px",
                          height: "22px",
                          borderRadius: "999px",
                          border: "1px solid #1f2937",
                          background: "#020617",
                          color: "#e5e7eb",
                          fontSize: "12px",
                          cursor: "pointer",
                          flexShrink: 0
                        }}
                        title="More information about the robots.txt check"
                      >
                        i
                      </button>
                    </li>
                    <li
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: "8px"
                      }}
                    >
                      <div>
                        <strong>sitemap.xml:</strong>{" "}
                        <span
                          style={{
                            color: result.sitemap?.found ? "#e5e7eb" : "#f97316"
                          }}
                        >
                          {result.sitemap?.found ? "Present" : "Missing"}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setHighlightInfoKey("sitemap")}
                        style={{
                          width: "22px",
                          height: "22px",
                          borderRadius: "999px",
                          border: "1px solid #1f2937",
                          background: "#020617",
                          color: "#e5e7eb",
                          fontSize: "12px",
                          cursor: "pointer",
                          flexShrink: 0
                        }}
                        title="More information about the sitemap.xml check"
                      >
                        i
                      </button>
                    </li>
              </ul>

                  {highlightInfo && (
                    <div
                      style={{
                        marginTop: "12px",
                        padding: "12px",
                        borderRadius: "8px",
                        border: "1px solid #1f2937",
                        background: "#020617"
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          marginBottom: "4px"
                        }}
                      >
                        <h3 style={{ margin: 0, fontSize: "15px" }}>{highlightInfo.title}</h3>
                        <button
                          type="button"
                          onClick={() => setHighlightInfoKey(null)}
                          style={{
                            border: "none",
                            background: "transparent",
                            color: "#9ca3af",
                            cursor: "pointer",
                            fontSize: "14px"
                          }}
                          title="Close information"
                        >
                          ×
                        </button>
                      </div>
                      <p style={{ margin: "0 0 6px", fontSize: "13px", color: "#cbd5f5" }}>
                        {highlightInfo.description}
                      </p>
                      <p style={{ margin: "0 0 6px", fontSize: "13px", color: "#e5e7eb" }}>
                        <strong>Why it matters:</strong> {highlightInfo.importance}
                      </p>
                      {Array.isArray(highlightInfo.details) && highlightInfo.details.length > 0 && (
                        <ul style={{ margin: 0, paddingLeft: "18px", fontSize: "13px", color: "#e5e7eb" }}>
                          {highlightInfo.details.map((d, idx) => (
                            <li key={idx}>{d}</li>
                          ))}
              </ul>
                      )}
                    </div>
                  )}
            </section>

                {positiveInsights.length > 0 && (
              <section
                style={{
                  background: "#0b1224",
                  border: "1px solid #1b2440",
                  borderRadius: "8px",
                  padding: "16px"
                }}
              >
                    <h2 style={{ marginTop: 0, fontSize: "18px" }}>Strengths (what already works well)</h2>
                    <p style={{ margin: "0 0 8px", fontSize: "13px", color: "#9ca3af" }}>
                      These are areas that look healthy based on the current analysis. In most cases, you shouldn’t
                      change them unless you have a very specific reason.
                    </p>
                    <ul style={{ margin: 0, paddingLeft: "16px", fontSize: "13px", color: "#bbf7d0" }}>
                      {positiveInsights.map((msg, idx) => (
                        <li
                          key={idx}
                          style={{
                            marginBottom: 4,
                            fontFamily:
                              "SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace"
                          }}
                        >
                          {msg}
                        </li>
                  ))}
                </ul>
              </section>
            )}

            <section
              style={{
                background: "#0b1224",
                border: "1px solid #1b2440",
                borderRadius: "8px",
                padding: "16px"
              }}
            >
                  <h2 style={{ marginTop: 0, fontSize: "18px" }}>Advanced SEO analysis (by category)</h2>
                  {advancedInsights.length > 0 ? (
                    <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "14px" }}>
                      {advancedInsights.map((group, idx) => (
                        <div key={idx}>
                          <h3 style={{ margin: "0 0 2px", fontSize: "14px", color: "#e5e7eb", display: "flex", alignItems: "center", gap: 6 }}>
                            {group.category === "social" && <IconTwitterX />}
                            {CATEGORY_LABELS[group.category] || group.category}
                          </h3>
                          <ul style={{ margin: 0, paddingLeft: "16px", fontSize: "13px", color: "#cbd5f5" }}>
                            {group.items.slice(0, 2).map((rec, rIdx) => (
                              <li key={rIdx} style={{ marginBottom: "4px" }}>
                                <div
                                  style={{
                                    fontFamily:
                                      "SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace",
                                    fontSize: "12px",
                                    color: "#f97316"
                                  }}
                                >
                                  {rec.message}
                                </div>
                                {rec.purpose && (
                                  <div style={{ fontSize: "12px", color: "#9ca3af", marginTop: "2px" }}>
                                    Purpose: {rec.purpose}
                                  </div>
                                )}
                              </li>
                            ))}
                            {group.items.length > 2 && (
                              <li style={{ marginTop: "2px", color: "#9ca3af", fontStyle: "italic" }}>
                                + {group.items.length - 2} more suggestions in this area.
                              </li>
                            )}
                          </ul>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p style={{ margin: 0, color: "#9ca3af" }}>
                      No additional issues detected. This page already follows most basic on‑page SEO best practices.
                    </p>
                  )}
            </section>

            {result.recommendations?.length > 0 && (
              <section
                style={{
                  background: "#0b1224",
                  border: "1px solid #1b2440",
                  borderRadius: "8px",
                  padding: "16px"
                }}
              >
                    <h2 style={{ marginTop: 0, fontSize: "18px" }}>Backend recommendations (full list)</h2>
                    <p style={{ margin: "0 0 6px", fontSize: "13px", color: "#9ca3af" }}>
                      This is the complete list of suggestions generated by the backend. Use the SEO score and
                      advanced analysis above to focus on the most important items first.
                    </p>
                    <ul style={{ margin: 0, paddingLeft: "16px", fontSize: "13px", color: "#d1d5db" }}>
                  {result.recommendations.map((rec, idx) => (
                        <li key={idx}>
                          <span
                            style={{
                              fontFamily:
                                "SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace",
                              fontSize: "12px",
                              color: "#f97316"
                            }}
                          >
                            {rec}
                          </span>
                        </li>
                  ))}
                </ul>
              </section>
                )}
              </>
            )}

            {analysisMode === "json" && (
            <section
              style={{
                background: "#0b1224",
                border: "1px solid #1b2440",
                borderRadius: "8px",
                padding: "16px"
              }}
            >
                <h2 style={{ marginTop: 0, fontSize: "18px" }}>Raw JSON (API result)</h2>
                <p style={{ marginTop: 0, marginBottom: "8px", color: "#9ca3af" }}>
                  This is the full JSON payload returned by the backend. You can use it for debugging,
                  exporting data or building custom SEO reports.
                </p>
              <PrettyJSON data={result} />
            </section>
            )}
          </div>
        )}
        {showScoreDetails && seoScore && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              zIndex: 40,
              display: "flex",
              alignItems: "flex-start",
              justifyContent: "center",
              padding: "80px 16px",
              background: "rgba(15,23,42,0.75)"
            }}
            onClick={() => setShowScoreDetails(false)}
          >
            <div
              onClick={(e) => e.stopPropagation()}
              style={{
                width: "100%",
                maxWidth: "520px",
                background: "#020617",
                borderRadius: "12px",
                border: "1px solid #1f2937",
                boxShadow: "0 18px 40px rgba(0,0,0,0.6)",
                padding: "16px 18px",
                color: "#e5e7eb"
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "6px"
                }}
              >
                <h2 style={{ margin: 0, fontSize: "17px" }}>SEO score details</h2>
                <button
                  type="button"
                  onClick={() => setShowScoreDetails(false)}
                  style={{
                    border: "none",
                    background: "transparent",
                    color: "#9ca3af",
                    cursor: "pointer",
                    fontSize: "16px"
                  }}
                  title="Close"
                >
                  ×
                </button>
      </div>
              <p style={{ margin: "0 0 8px", fontSize: "13px", color: "#cbd5f5" }}>
                The score starts at <strong>{seoScore.baseScore}</strong> and subtracts points for issues in
                different SEO areas. More issues or more important issues in a category lead to a bigger penalty.
              </p>
              <p style={{ margin: "0 0 6px", fontSize: "13px", color: "#9ca3af" }}>
                <strong>Final score:</strong> {seoScore.score}/100 ({seoScore.grade}) &middot;{" "}
                <strong>Total penalty:</strong> {seoScore.totalPenalty} points
              </p>
              <div
                style={{
                  margin: "0 0 10px",
                  padding: "6px 8px",
                  borderRadius: "8px",
                  background: "#020617",
                  border: "1px solid #1f2937"
                }}
              >
                <div
                  style={{
                    fontSize: "12px",
                    color: "#9ca3af",
                    marginBottom: 4,
                    display: "flex",
                    justifyContent: "space-between"
                  }}
                >
                  <span>Overall SEO score</span>
                  <span>{seoScore.score}/100</span>
                </div>
                <div
                  style={{
                    width: "100%",
                    height: "8px",
                    borderRadius: 999,
                    background: "#020617",
                    overflow: "hidden",
                    border: "1px solid #111827"
                  }}
                >
                  <div
                    style={{
                      width: `${seoScore.score}%`,
                      height: "100%",
                      background:
                        seoScore.score >= 85
                          ? "linear-gradient(90deg,#22c55e,#4ade80)"
                          : seoScore.score >= 70
                          ? "linear-gradient(90deg,#eab308,#fbbf24)"
                          : "linear-gradient(90deg,#ef4444,#f97316)"
                    }}
                  />
                </div>
              </div>

              <h3 style={{ margin: "0 0 4px", fontSize: "14px" }}>Per‑category impact</h3>
              <ul style={{ margin: 0, paddingLeft: "0", fontSize: "13px", color: "#d1d5db", listStyle: "none" }}>
                {seoScore.breakdown.map((item, idx) => {
                  const share =
                    seoScore.totalPenalty > 0 ? Math.max(8, (item.penalty / seoScore.totalPenalty) * 100) : 0;
                  return (
                    <li key={idx} style={{ marginBottom: 6 }}>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          marginBottom: 2
                        }}
                      >
                        <span>{item.label}</span>
                        <span style={{ fontSize: "12px", color: "#9ca3af" }}>
                          −{item.penalty} ({item.issues} issue{item.issues > 1 ? "s" : ""})
                        </span>
                      </div>
                      <div
                        style={{
                          width: "100%",
                          height: "6px",
                          borderRadius: 999,
                          background: "#020617",
                          overflow: "hidden",
                          border: "1px solid #111827"
                        }}
                      >
                        <div
                          style={{
                            width: `${share}%`,
                            height: "100%",
                            background: "#ef4444"
                          }}
                        />
                      </div>
                    </li>
                  );
                })}
              </ul>
              <p style={{ margin: "10px 0 0", fontSize: "12px", color: "#9ca3af" }}>
                Use this breakdown together with the advanced analysis to decide which areas to improve first.
                Fixing high‑penalty categories (like technical, performance and content) will usually have the
                biggest impact on the score.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

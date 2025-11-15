import React, { useMemo, useState } from "react";

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

export default function App() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [analysisMode, setAnalysisMode] = useState("html"); // "html" | "json"

  const valid = isLikelyUrl(url);
  const advancedInsights = useMemo(() => getAdvancedSeoInsights(result), [result]);
  const categoryLabels = {
    title: "Title tag",
    meta_description: "Meta description",
    headings: "Headings (H1)",
    content: "Content",
    images: "Images",
    links: "Links",
    technical: "Technical SEO",
    canonical: "Canonicalization",
    internationalization: "Language / international targeting",
    social: "Social sharing (Open Graph & Twitter Cards)"
  };

  async function handleAnalyze(e) {
    e.preventDefault();
    setError("");
    setResult(null);
    if (!valid) {
      setError("Please enter a valid URL (e.g., example.com or https://example.com).");
      return;
    }
    setLoading(true);
    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url })
      });
      const json = await response.json();
      if (!response.ok || !json.ok) {
        throw new Error(json?.detail || "Analysis failed");
      }
      setResult(json.data);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "linear-gradient(180deg,#0f172a 0%, #0b1020 100%)",
        color: "#e2e8f0"
      }}
    >
      <div style={{ maxWidth: "960px", margin: "0 auto", padding: "32px 16px" }}>
        <header style={{ marginBottom: "24px" }}>
          <h1 style={{ margin: 0, fontSize: "28px" }}>SEO Analyzer</h1>
          <p style={{ margin: "8px 0 0", color: "#94a3b8" }}>
            Enter a website URL to analyze on-page SEO elements.
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
              background: "#2a0b0b",
              border: "1px solid #4b1111",
              color: "#fecaca",
              padding: "12px",
              borderRadius: "8px",
              marginBottom: "16px"
            }}
          >
            {error}
          </div>
        )}

        {result && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "16px" }}>
            <section
              style={{
                background: "#0b1224",
                border: "1px solid #1b2440",
                borderRadius: "8px",
                padding: "16px"
              }}
            >
              <h2 style={{ marginTop: 0, fontSize: "18px" }}>Summary</h2>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                <div><strong>Final URL:</strong> {result.final_url}</div>
                <div><strong>Status:</strong> {result.http?.status_code}</div>
                <div><strong>Response time:</strong> {result.http?.response_time_seconds}s</div>
                <div><strong>Content length:</strong> {result.http?.content_length_bytes} bytes</div>
              </div>
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
                  <h2 style={{ marginTop: 0, fontSize: "18px" }}>Highlights (HTML)</h2>
                  <ul style={{ margin: 0, paddingLeft: "16px" }}>
                    <li><strong>Title (HTML &lt;title&gt;):</strong> {result.html?.title?.text || "—"} ({result.html?.title?.length} chars)</li>
                    <li><strong>Meta description:</strong> {result.html?.meta_description?.text || "—"}</li>
                    <li><strong>H1 count:</strong> {result.html?.h1?.count}</li>
                    <li><strong>Canonical:</strong> {result.html?.canonical || "—"}</li>
                    <li><strong>Language:</strong> {result.html?.lang || "—"}</li>
                    <li><strong>Word count:</strong> {result.html?.word_count}</li>
                    <li><strong>Images without alt:</strong> {result.html?.images?.without_alt_count}</li>
                    <li><strong>Open Graph tags (og:*):</strong> {result.html?.open_graph_present ? "Present" : "Missing"}</li>
                    <li><strong>Twitter Card tags:</strong> {result.html?.twitter_card_present ? "Present" : "Missing"}</li>
                    <li><strong>Internal links:</strong> {result.links?.internal_count}</li>
                    <li><strong>External links:</strong> {result.links?.external_count}</li>
                    <li><strong>robots.txt:</strong> {result.robots?.has_robots ? "Present" : "Missing"}</li>
                    <li><strong>sitemap.xml:</strong> {result.sitemap?.found ? "Present" : "Missing"}</li>
                  </ul>
                </section>

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
                    <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "12px" }}>
                      {advancedInsights.map((group, idx) => (
                        <div key={idx}>
                          <h3 style={{ margin: "0 0 4px", fontSize: "15px" }}>
                            {categoryLabels[group.category] || group.category}
                          </h3>
                          <ul style={{ margin: 0, paddingLeft: "16px" }}>
                            {group.items.map((rec, rIdx) => (
                              <li key={rIdx}>
                                <div>{rec.message}</div>
                                {rec.purpose && (
                                  <div style={{ fontSize: "12px", color: "#9ca3af", marginTop: "2px" }}>
                                    Purpose: {rec.purpose}
                                  </div>
                                )}
                              </li>
                            ))}
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
                    <h2 style={{ marginTop: 0, fontSize: "18px" }}>Backend recommendations</h2>
                    <ul style={{ margin: 0, paddingLeft: "16px" }}>
                      {result.recommendations.map((rec, idx) => (
                        <li key={idx}>{rec}</li>
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
      </div>
    </div>
  );
}

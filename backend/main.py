from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict
from urllib.parse import urlparse
import os

from .seo_analyzer import analyze_url, normalize_url


class AnalyzeRequest(BaseModel):
    url: str


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


@app.post("/api/analyze")
def analyze(request: AnalyzeRequest) -> Dict[str, Any]:
    # Normalize common paste issues (handled in normalize_url) and then
    # perform clear, user-friendly validation here.
    raw_url = (request.url or "").strip()
    target_url = normalize_url(raw_url)

    parsed = urlparse(target_url)

    # Specific, user-facing error messages:
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

    try:
        result = analyze_url(target_url)
        return {"ok": True, "data": result}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)




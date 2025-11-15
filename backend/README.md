# SEO Analyzer Backend (FastAPI)

## Setup

1) Create and activate a virtual environment (recommended)
```
python -m venv .venv
.venv\Scripts\activate
```

2) Install dependencies
```
pip install -r backend/requirements.txt
```

3) Run the API
```
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:
- Docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/api/health

## Environment

- You can set `ALLOWED_ORIGINS` (comma-separated) to control CORS.

## Endpoint

- POST `/api/analyze`
  - Body: `{ "url": "https://example.com" }`
  - Response: `{ "ok": true, "data": { ...analysis... } }`






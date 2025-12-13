import os
from typing import Optional

import requests


class GeminiError(Exception):
    """Errors raised when calling the Gemini API."""


GEMINI_API_BASE = os.getenv(
    "GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta"
)


def gemini_chat(
    model: str,
    prompt: str,
    api_key: str,
    temperature: float = 0.3,
) -> str:
    """
    Minimal wrapper around Google's Generative Language REST API (Gemini).

    We send a single user prompt and return the concatenated text from the
    first candidate's content parts.
    """
    if not api_key:
        raise GeminiError("GEMINI_API_KEY is not set.")

    url = f"{GEMINI_API_BASE.rstrip('/')}/models/{model}:generateContent"
    headers = {"Content-Type": "application/json"}
    params = {"key": api_key}

    body = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": temperature,
        },
    }

    try:
        resp = requests.post(url, headers=headers, params=params, json=body, timeout=60)
    except Exception as exc:
        raise GeminiError(f"Failed to reach Gemini at {url}: {exc}") from exc

    if resp.status_code != 200:
        raise GeminiError(f"Gemini returned {resp.status_code}: {resp.text}")

    data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise GeminiError("Gemini response contained no candidates.")

    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    text_chunks = []
    for part in parts:
        t = part.get("text")
        if isinstance(t, str):
            text_chunks.append(t)

    full_text = "".join(text_chunks).strip()
    if not full_text:
        raise GeminiError("Gemini response did not contain any text parts.")
    return full_text





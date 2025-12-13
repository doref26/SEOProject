import os
from typing import Dict, List

import requests


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


class OllamaError(Exception):
    pass


def ollama_chat(model: str, messages: List[Dict[str, str]], temperature: float = 0.4) -> str:
    """
    Minimal client for Ollama's /api/chat endpoint.

    Expects the Ollama daemon to be running locally, e.g.:
        ollama pull llama3.1
        ollama serve
    """
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"
    try:
        resp = requests.post(
            url,
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": temperature},
            },
        )
    except Exception as exc:
        raise OllamaError(f"Failed to reach Ollama at {url}: {exc}") from exc

    if resp.status_code != 200:
        raise OllamaError(f"Ollama returned {resp.status_code}: {resp.text}")

    data = resp.json()
    message = data.get("message") or {}
    content = message.get("content") or ""
    if not isinstance(content, str):
        raise OllamaError("Ollama response did not contain a valid 'message.content' string.")
    return content


def ollama_embed(model: str, text: str) -> List[float]:
    """
    Call Ollama's /api/embeddings endpoint to get an embedding vector.

    Requires an embedding-capable model to be pulled, for example:
        ollama pull nomic-embed-text
    """
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/embeddings"
    try:
        resp = requests.post(
            url,
            json={
                "model": model,
                "prompt": text,
            },
        )
    except Exception as exc:
        raise OllamaError(f"Failed to reach Ollama embeddings at {url}: {exc}") from exc

    if resp.status_code != 200:
        raise OllamaError(f"Ollama embeddings returned {resp.status_code}: {resp.text}")

    data = resp.json()
    embedding = data.get("embedding")
    if not isinstance(embedding, list):
        raise OllamaError("Ollama embeddings response did not contain a valid 'embedding' list.")
    return [float(x) for x in embedding]




import json
import os
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel


SETTINGS_PATH = Path(__file__).resolve().parent / "settings.json"
_current_settings: Optional["AppSettings"] = None


class AppSettings(BaseModel):
    """
    Simple app-level settings that can be controlled from the frontend.

    These settings are also mirrored into environment variables so that
    RAGConfig (which reads from env) picks up changes without restarting.
    """

    use_llm_default: bool = True
    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")  # 'openai' or 'ollama'
    embedding_backend: str = os.getenv("EMBEDDING_BACKEND", "openai")  # 'openai' | 'local' | 'ollama'
    local_llm_model: str = os.getenv("LOCAL_LLM_MODEL", "llama3.1")
    ollama_embed_model: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    openai_embedding_model: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


def _apply_to_env(settings: AppSettings) -> None:
    """
    Mirror relevant settings into os.environ so that RAGConfig (which uses
    environment variables) sees the updated values.
    """
    os.environ["LLM_PROVIDER"] = settings.llm_provider
    os.environ["EMBEDDING_BACKEND"] = settings.embedding_backend
    os.environ["LOCAL_LLM_MODEL"] = settings.local_llm_model
    os.environ["OLLAMA_EMBED_MODEL"] = settings.ollama_embed_model
    os.environ["OPENAI_MODEL"] = settings.openai_model
    os.environ["OPENAI_EMBEDDING_MODEL"] = settings.openai_embedding_model


def load_settings() -> AppSettings:
    """
    Load settings from disk (if present) and apply them to the environment.
    """
    global _current_settings
    base = AppSettings()
    if SETTINGS_PATH.exists():
        try:
            raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            # Merge file values on top of defaults
            base = AppSettings(**{**base.model_dump(), **raw})
        except Exception:
            # If the file is corrupted, ignore and fall back to defaults.
            pass
    _apply_to_env(base)
    _current_settings = base
    return base


def get_settings() -> AppSettings:
    global _current_settings
    if _current_settings is None:
        return load_settings()
    return _current_settings


def update_settings(patch: dict[str, Any]) -> AppSettings:
    """
    Update current settings with the provided partial patch, persist to disk,
    and mirror into environment variables.
    """
    global _current_settings
    current = get_settings()
    updated = current.model_copy(update=patch)
    SETTINGS_PATH.write_text(updated.model_dump_json(indent=2), encoding="utf-8")
    _apply_to_env(updated)
    _current_settings = updated
    return updated




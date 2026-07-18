"""Embedding selection for OpenAI and Claude-only installations."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _openai_key_configured() -> bool:
    value = os.getenv("OPENAI_API_KEY", "").strip()
    return bool(value and not value.casefold().startswith("replace_"))


def embedding_provider() -> str:
    requested = os.getenv("EMBEDDING_PROVIDER", "auto").strip().casefold()
    if requested not in {"auto", "openai", "local"}:
        raise ValueError("EMBEDDING_PROVIDER must be auto, openai, or local.")
    if requested == "auto":
        return "openai" if _openai_key_configured() else "local"
    if requested == "openai" and not _openai_key_configured():
        raise RuntimeError("EMBEDDING_PROVIDER is openai but OPENAI_API_KEY is not configured.")
    return requested


def collection_name() -> str:
    configured = os.getenv("CHROMA_COLLECTION", "").strip()
    if configured:
        return configured
    # Local and OpenAI embeddings have different dimensions, so keep their
    # collections separate when users switch model providers.
    return "assistant_memory" if embedding_provider() == "openai" else "assistant_memory_local"


def get_embedding(text: str) -> list[float]:
    if embedding_provider() == "openai":
        from openai import OpenAI

        response = OpenAI().embeddings.create(
            model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            input=text,
        )
        return response.data[0].embedding

    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

    values = DefaultEmbeddingFunction()([text])
    return values[0].tolist() if hasattr(values[0], "tolist") else list(values[0])

"""Thin async wrapper over google-genai. Every call has a timeout and returns None on
failure so callers can fall back to canned output (never dead air on stage)."""
import asyncio
import json
import logging
from typing import Any, Optional, Type

from pydantic import BaseModel

from app.config import get_settings

log = logging.getLogger("ithaca.gemini")
_client = None


def client():
    global _client
    s = get_settings()
    if not s.has_gemini:
        return None
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=s.gemini_api_key)
    return _client


async def generate_json(
    prompt: str,
    schema: Type[BaseModel],
    *,
    images: Optional[list[tuple[bytes, str]]] = None,
    system: Optional[str] = None,
    timeout: float = 10.0,
    temperature: float = 0.7,
) -> Optional[BaseModel]:
    """Structured output. images = [(bytes, mime_type)]."""
    c = client()
    if c is None:
        return None
    from google.genai import types

    parts: list[Any] = [types.Part.from_bytes(data=b, mime_type=m) for b, m in (images or [])]
    parts.append(prompt)
    cfg = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema,
        temperature=temperature,
        system_instruction=system,
    )
    try:
        resp = await asyncio.wait_for(
            c.aio.models.generate_content(model=get_settings().gemini_model, contents=parts, config=cfg),
            timeout=timeout,
        )
        if resp.parsed is not None:
            return resp.parsed
        return schema.model_validate(json.loads(resp.text))
    except Exception as e:  # timeout, quota, bad JSON...
        log.warning("gemini generate_json failed: %r", e)
        return None


async def embed(texts: list[str], *, task: str = "RETRIEVAL_DOCUMENT", timeout: float = 15.0) -> Optional[list[list[float]]]:
    c = client()
    if c is None or not texts:
        return None
    from google.genai import types

    s = get_settings()
    try:
        resp = await asyncio.wait_for(
            c.aio.models.embed_content(
                model=s.gemini_embed_model,
                contents=texts,
                config=types.EmbedContentConfig(task_type=task, output_dimensionality=s.embed_dim),
            ),
            timeout=timeout,
        )
        return [list(e.values) for e in resp.embeddings]
    except Exception as e:
        log.warning("gemini embed failed: %r", e)
        return None

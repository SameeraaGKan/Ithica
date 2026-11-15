"""Local vision via Ollama (small model, no cloud). Same contract as gemini.generate_json: returns a parsed
pydantic object, or None on any failure so the caller can try the next provider."""
import base64
import io
import logging
from typing import Optional, Type

import httpx
from pydantic import BaseModel

from app.config import get_settings

log = logging.getLogger("ithaca.local_vision")


def _small_jpeg(b: bytes) -> bytes:
    """Smaller image = fewer vision tokens = faster on a small local model."""
    from PIL import Image  # imported here so a missing Pillow can't stop the whole API from starting
    img = Image.open(io.BytesIO(b)).convert("RGB")
    img.thumbnail((448, 448))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=80)
    return out.getvalue()


async def generate_json(prompt: str, schema: Type[BaseModel], *, images: Optional[list[tuple[bytes, str]]] = None,
                        system: Optional[str] = None, timeout: float = 10.0, temperature: float = 0.7) -> Optional[BaseModel]:
    s = get_settings()
    if not s.ollama_url:
        return None
    del timeout  # the Ollama budget is ollama_timeout_s, not the Gemini one
    try:
        imgs = [base64.b64encode(_small_jpeg(b)).decode() for b, _ in (images or [])]
    except Exception as e:  # Pillow missing or an unreadable frame: let the next provider try
        log.warning("local vision skipped: %r", e)
        return None
    msgs = ([{"role": "system", "content": system}] if system else []) + [{
        "role": "user",
        "content": prompt + "\nReply with JSON only.",
        "images": imgs,
    }]
    body = {"model": s.ollama_vision_model, "stream": False, "messages": msgs,
            "format": schema.model_json_schema(), "keep_alive": "30m", "options": {"temperature": temperature, "num_predict": 300}}
    try:
        async with httpx.AsyncClient(base_url=s.ollama_url, timeout=s.ollama_timeout_s) as c:
            r = await c.post("/api/chat", json=body)
            r.raise_for_status()
            return schema.model_validate_json(r.json()["message"]["content"])
    except Exception as e:
        log.warning("ollama vision failed: %r", e)
        return None

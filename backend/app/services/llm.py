"""Text generation with providers in order: Gemini first, then the local Ollama model.
Each provider returns a parsed pydantic object or None, so the next one gets a turn."""
from typing import Optional, Type

from pydantic import BaseModel

from app.config import get_settings
from app.services import gemini, local_vision


async def generate_json(prompt: str, schema: Type[BaseModel], *, system: Optional[str] = None,
                        timeout: float = 10.0, temperature: float = 0.7) -> Optional[BaseModel]:
    for name in get_settings().text_providers.split(","):
        name = name.strip()
        call = gemini.generate_json if name == "gemini" else local_vision.generate_json if name == "ollama" else None
        if call is None:
            continue
        res = await call(prompt, schema, system=system, timeout=timeout, temperature=temperature)
        if res is not None:
            return res
    return None

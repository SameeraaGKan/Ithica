"""ElevenLabs TTS for Bard episodes. Audio is cached by content hash, so each
era/path episode is generated once and served as a static file afterwards."""
import hashlib
import logging
from typing import Optional

import httpx

from app.config import get_settings

log = logging.getLogger("ithaca.tts")


def _key(text: str, voice: str) -> str:
    return hashlib.sha1(f"{voice}:{text}".encode()).hexdigest()[:16]


async def narrate(text: str, *, voice_id: Optional[str] = None, timeout: float = 30.0) -> Optional[str]:
    """Returns a public URL to an mp3, or None if TTS is unavailable."""
    s = get_settings()
    voice = voice_id or s.elevenlabs_voice_id
    s.audio_dir.mkdir(parents=True, exist_ok=True)
    name = f"{_key(text, voice)}.mp3"
    path = s.audio_dir / name
    url = f"{s.public_base_url.rstrip('/')}/static/audio/{name}"
    if path.exists() and path.stat().st_size > 0:
        return url
    if not s.has_elevenlabs:
        return None
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
                params={"output_format": "mp3_44100_128"},
                headers={"xi-api-key": s.elevenlabs_api_key, "accept": "audio/mpeg"},
                json={
                    "text": text,
                    "model_id": s.elevenlabs_model,
                    "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.35},
                },
            )
            r.raise_for_status()
            path.write_bytes(r.content)
            return url
    except Exception as e:
        log.warning("elevenlabs tts failed: %r", e)
        return None

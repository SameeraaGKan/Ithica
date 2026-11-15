"""ElevenLabs TTS for Bard episodes. Audio is cached by content hash, so each
era/path episode is generated once and served as a static file afterwards."""
import asyncio
import hashlib
import logging
import shutil
import sys
from typing import Optional

import httpx

from app.config import get_settings

log = logging.getLogger("ithaca.tts")


def _key(text: str, voice: str) -> str:
    return hashlib.sha1(f"{voice}:{text}".encode()).hexdigest()[:16]


async def _win_speech(text: str, out_wav) -> bool:
    """Windows built-in voice (System.Speech via PowerShell), straight to WAV. Text goes in an env var, not the command line."""
    import os
    ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          "$s.SetOutputToWaveFile($env:ITHACA_OUT); $s.Speak($env:ITHACA_TEXT); $s.Dispose()")
    env = {**os.environ, "ITHACA_TEXT": text, "ITHACA_OUT": str(out_wav)}
    p = await asyncio.create_subprocess_exec("powershell", "-NoProfile", "-NonInteractive", "-Command", ps,
                                             env=env, stderr=asyncio.subprocess.PIPE)
    await p.wait()
    return p.returncode == 0 and out_wav.exists() and out_wav.stat().st_size > 0


async def _mac_say(text: str, out_wav) -> bool:
    """Offline fallback: the macOS built-in voice (`say`), converted to WAV with `afconvert`. No account, no install."""
    if sys.platform == "win32":
        return await _win_speech(text, out_wav)
    if sys.platform != "darwin" or not shutil.which("say") or not shutil.which("afconvert"):
        return False
    aiff = out_wav.with_suffix(".aiff")
    try:
        for args in (["say", "-v", "Daniel", "-o", str(aiff), text], ["say", "-o", str(aiff), text]):
            p = await asyncio.create_subprocess_exec(*args, stderr=asyncio.subprocess.PIPE)
            if await p.wait() == 0 and aiff.exists():
                break
        else:
            return False
        p = await asyncio.create_subprocess_exec("afconvert", "-f", "WAVE", "-d", "LEI16", str(aiff), str(out_wav))
        ok = await p.wait() == 0 and out_wav.exists() and out_wav.stat().st_size > 0
        return ok
    finally:
        aiff.unlink(missing_ok=True)


async def narrate(text: str, *, voice_id: Optional[str] = None, timeout: float = 30.0,
                  local_fallback: bool = True) -> Optional[str]:
    """Returns a public URL to the audio, or None if no voice is available.
    Order: ElevenLabs (mp3), then the computer's built-in voice (wav: macOS `say` or Windows System.Speech)."""
    s = get_settings()
    voice = voice_id or s.elevenlabs_voice_id
    s.audio_dir.mkdir(parents=True, exist_ok=True)
    stem = _key(text, voice)
    for ext in ((".mp3", ".wav") if local_fallback else (".mp3",)):
        cached = s.audio_dir / f"{stem}{ext}"
        if cached.exists() and cached.stat().st_size > 0:
            return f"{s.public_base_url.rstrip('/')}/static/audio/{cached.name}"
    path = s.audio_dir / f"{stem}.mp3"
    url = f"{s.public_base_url.rstrip('/')}/static/audio/{path.name}"
    if s.has_elevenlabs:
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
                if r.status_code >= 400:
                    # e.g. 401 missing_permissions (key lacks Text to Speech) or 404 voice_not_found
                    log.warning("elevenlabs tts failed %s: %s", r.status_code, r.text[:300])
                else:
                    path.write_bytes(r.content)
                    return url
        except Exception as e:
            log.warning("elevenlabs tts failed: %r", e)
    wav = s.audio_dir / f"{stem}.wav"
    if local_fallback and await _mac_say(text, wav):
        return f"{s.public_base_url.rstrip('/')}/static/audio/{wav.name}"
    return None

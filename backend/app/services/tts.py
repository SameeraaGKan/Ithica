"""Bard narration. Audio is cached by content hash, so each line is generated once and served as a static file.

Order: ElevenLabs (mp3) -> Gemini TTS (natural voice, free tier, same key as the scripts) -> the computer's built-in
voice (episodes only; it sounds robotic). Files say which voice made them: .mp3 ElevenLabs, .gem.wav Gemini,
.os.wav built-in, so a robotic file never blocks a better voice later."""
import asyncio
import hashlib
import logging
import shutil
import sys
import wave
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


_elevenlabs_out = False  # set when ElevenLabs says the quota is used up: stop spending calls on it this run


async def _elevenlabs(text: str, voice: str, path, timeout: float) -> bool:
    global _elevenlabs_out
    s = get_settings()
    if not s.has_elevenlabs or _elevenlabs_out:
        return False
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
                params={"output_format": "mp3_44100_128"},
                headers={"xi-api-key": s.elevenlabs_api_key, "accept": "audio/mpeg"},
                json={"text": text, "model_id": s.elevenlabs_model,
                      "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.35}},
            )
        if r.status_code >= 400:
            # e.g. 401 missing_permissions (key lacks Text to Speech), quota_exceeded, or 404 voice_not_found
            log.warning("elevenlabs tts failed %s: %s", r.status_code, r.text[:300])
            if "quota_exceeded" in r.text:
                _elevenlabs_out = True
                log.warning("ElevenLabs credits are used up: narrating with Gemini TTS instead")
            return False
        path.write_bytes(r.content)
        return True
    except Exception as e:
        log.warning("elevenlabs tts failed: %r", e)
        return False


async def _gemini_tts(text: str, out_wav, timeout: float) -> bool:
    """Gemini speech generation: 24 kHz 16-bit mono PCM, wrapped as WAV."""
    from app.services import gemini
    s = get_settings()
    c = gemini.client()
    if c is None:
        return False
    from google.genai import types
    models = list(dict.fromkeys([s.gemini_tts_model, "gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts"]))
    for model in models:
        try:
            r = await asyncio.wait_for(c.aio.models.generate_content(
                model=model,
                contents=f"Read this like a warm, epic storyteller, unhurried and vivid: {text}",
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=s.gemini_tts_voice))),
                ),
            ), timeout=timeout)
            pcm = r.candidates[0].content.parts[0].inline_data.data
            if isinstance(pcm, str):
                import base64
                pcm = base64.b64decode(pcm)
            if not pcm:
                continue
            with wave.open(str(out_wav), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(24000)
                w.writeframes(pcm)
            return True
        except Exception as e:
            log.warning("gemini tts (%s) failed: %r", model, e)
            out_wav.unlink(missing_ok=True)
            if "404" not in str(e) and "not found" not in str(e).lower():
                break  # quota / rate limit / network: another model won't help
    return False


def is_good_voice(url: Optional[str]) -> bool:
    """True for ElevenLabs or Gemini audio; False for the robotic built-in voice (or none)."""
    return bool(url) and (url.endswith(".mp3") or url.endswith(".gem.wav"))


async def narrate(text: str, *, voice_id: Optional[str] = None, timeout: float = 30.0,
                  local_fallback: bool = True) -> Optional[str]:
    """Returns a public URL to the audio, or None if no voice is available (see module docstring for the order)."""
    s = get_settings()
    voice = voice_id or s.elevenlabs_voice_id
    s.audio_dir.mkdir(parents=True, exist_ok=True)
    stem = _key(text, voice)
    base = f"{s.public_base_url.rstrip('/')}/static/audio/"
    for name in (f"{stem}.mp3", f"{stem}.gem.wav"):
        cached = s.audio_dir / name
        if cached.exists() and cached.stat().st_size > 0:
            return base + name
    for provider in (p.strip() for p in s.tts_providers.split(",")):
        if provider == "elevenlabs" and await _elevenlabs(text, voice, s.audio_dir / f"{stem}.mp3", timeout):
            return base + f"{stem}.mp3"
        if provider == "gemini" and await _gemini_tts(text, s.audio_dir / f"{stem}.gem.wav", timeout):
            return base + f"{stem}.gem.wav"
    if not local_fallback:
        return None
    os_wav = s.audio_dir / f"{stem}.os.wav"
    if (os_wav.exists() and os_wav.stat().st_size > 0) or await _mac_say(text, os_wav):
        return base + os_wav.name
    return None

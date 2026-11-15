import asyncio
import types as pytypes

from app.config import get_settings
from app.services import gemini, tts


def _fake_gemini(pcm: bytes):
    part = pytypes.SimpleNamespace(inline_data=pytypes.SimpleNamespace(data=pcm))
    resp = pytypes.SimpleNamespace(candidates=[pytypes.SimpleNamespace(content=pytypes.SimpleNamespace(parts=[part]))])

    async def generate_content(**kw):
        return resp

    return pytypes.SimpleNamespace(aio=pytypes.SimpleNamespace(models=pytypes.SimpleNamespace(generate_content=generate_content)))


def test_gemini_tts_when_elevenlabs_is_out(monkeypatch, tmp_path):
    s = get_settings()
    monkeypatch.setattr(s, "audio_dir", tmp_path)
    monkeypatch.setattr(tts, "_elevenlabs_out", True)  # credits used up
    monkeypatch.setattr(gemini, "client", lambda: _fake_gemini(b"\x00\x01" * 2400))
    url = asyncio.run(tts.narrate("Sing, Muse, of FaZe.", local_fallback=False))
    assert url and url.endswith(".gem.wav") and tts.is_good_voice(url)
    assert (tmp_path / url.rsplit("/", 1)[1]).stat().st_size > 44  # WAV header + audio


def test_no_voice_means_no_robot_for_intro(monkeypatch, tmp_path):
    s = get_settings()
    monkeypatch.setattr(s, "audio_dir", tmp_path)
    monkeypatch.setattr(tts, "_elevenlabs_out", True)
    monkeypatch.setattr(gemini, "client", lambda: None)
    assert asyncio.run(tts.narrate("x", local_fallback=False)) is None
    assert not tts.is_good_voice("http://h/static/audio/abc.os.wav")

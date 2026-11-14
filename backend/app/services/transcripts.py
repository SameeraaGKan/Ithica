"""Transcripts (P1): Whisper (faster-whisper, if installed) or Gemini audio transcription, or an
existing caption file (.vtt/.srt, e.g. shared by FaZe). Chunked into ~30s windows, embedded, and
stored in Atlas `transcript_chunks` (+ local data/transcripts.json fallback). Used by the Siren
("what's being said right now") and Ask the Bard (grounding)."""
import json
import logging
import re
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from app.config import BASE_DIR
from app.services import gemini

log = logging.getLogger("ithaca.transcripts")
LOCAL = BASE_DIR / "data" / "transcripts.json"
WINDOW_S = 30


class Seg(BaseModel):
    start: float
    end: float
    text: str


class _GemSegs(BaseModel):
    segments: list[Seg]


def _ts(s: str) -> float:
    s = s.strip().replace(",", ".")
    parts = [float(p) for p in s.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def parse_captions(text: str) -> list[Seg]:
    """WebVTT or SRT -> segments."""
    segs = []
    for block in re.split(r"\n\s*\n", text.replace("\r", "")):
        m = re.search(r"([\d:.,]+)\s*-->\s*([\d:.,]+)", block)
        if not m:
            continue
        body = block[m.end():].strip()
        body = re.sub(r"<[^>]+>", "", body)
        body = " ".join(l.strip() for l in body.splitlines() if l.strip())
        if body:
            segs.append(Seg(start=_ts(m.group(1)), end=_ts(m.group(2)), text=body))
    # YouTube auto-captions repeat lines across cues; drop exact consecutive repeats
    out: list[Seg] = []
    for sg in segs:
        if out and sg.text == out[-1].text:
            out[-1].end = sg.end
        else:
            out.append(sg)
    return out


def whisper(audio: Path) -> Optional[list[Seg]]:
    try:
        from faster_whisper import WhisperModel  # optional: pip install faster-whisper
    except ImportError:
        return None
    model = WhisperModel("small", device="auto", compute_type="int8")
    segments, _ = model.transcribe(str(audio), vad_filter=True)
    return [Seg(start=s.start, end=s.end, text=s.text.strip()) for s in segments]


async def gemini_transcribe(audio: Path) -> Optional[list[Seg]]:
    mime = {"mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4", "ogg": "audio/ogg", "webm": "audio/webm"}.get(
        audio.suffix.lstrip(".").lower(), "audio/mpeg")
    res = await gemini.generate_json(
        "Transcribe this audio. Return segments of about 5-15 seconds with start/end in seconds and the spoken text.",
        _GemSegs, images=[(audio.read_bytes(), mime)], timeout=180, temperature=0)
    return res.segments if res else None


def chunk(segs: list[Seg], window: int = WINDOW_S) -> list[dict]:
    chunks, cur, start = [], [], None
    for sg in segs:
        if start is None:
            start = sg.start
        cur.append(sg)
        if sg.end - start >= window:
            chunks.append({"start_s": int(start), "end_s": int(sg.end), "text": " ".join(x.text for x in cur)})
            cur, start = [], None
    if cur:
        chunks.append({"start_s": int(start), "end_s": int(cur[-1].end), "text": " ".join(x.text for x in cur)})
    return chunks


def load_local() -> list[dict]:
    if LOCAL.exists():
        return json.loads(LOCAL.read_text(encoding="utf-8"))
    return []


def save_local(video_id: str, chunks: list[dict]) -> None:
    rows = [r for r in load_local() if r["video_id"] != video_id] + [{"video_id": video_id, **c} for c in chunks]
    LOCAL.write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")

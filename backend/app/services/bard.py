"""The Bard: RAG over lore -> Gemini script -> ElevenLabs narration -> video cues.
Episodes are cached per (era, path, topic) so each costs one generation, ever."""
import hashlib
import json
import logging
from typing import Optional

from pydantic import BaseModel, Field

from app.config import get_settings
from app.schemas import ERA_LABELS, EpisodeResponse, VideoCue
from app.services import gemini, tts
from app.services.lore import lore

log = logging.getLogger("ithaca.bard")

BARD_SYSTEM = """You are the Bard of Ithaca: a Homeric storyteller who sings the history of FaZe Clan.
Voice: epic but warm and a little playful, like Demodocus singing at a feast; gamer-literate, never cringe.
Rules:
- Use ONLY facts in the provided LORE. Never invent dates, names, numbers, or quotes. If unsure, stay vague.
- 60 to 90 seconds spoken (about 150-220 words). Short lines that sound good read aloud. No stage directions, no emojis, no markdown.
- Weave in Odyssey imagery lightly (Ithaca = home, the long voyage, the bow, the suitors) without overdoing it.
- For path=odysseus (returning fan): "you were there" framing; welcome them home; name their era.
- For path=telemachus (new fan): "here is why this mattered" framing; hand them the legend they missed.
- End with one line that points to the next era or invites them to collect the relic."""


class _Script(BaseModel):
    title: str = Field(description="Short episode title, max 7 words")
    script: str = Field(description="The spoken narration")
    used_lore_ids: list[str]


_cache: dict[str, EpisodeResponse] = {}


def _cache_path():
    return get_settings().audio_dir.parent / "episodes.json"


def load_cache() -> None:
    p = _cache_path()
    if p.exists():
        try:
            for k, v in json.loads(p.read_text()).items():
                _cache[k] = EpisodeResponse.model_validate(v)
        except Exception as e:
            log.warning("episode cache unreadable: %r", e)


def _save_cache() -> None:
    p = _cache_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({k: v.model_dump() for k, v in _cache.items()}, indent=1))


def _template(era: str, path: str, entries: list[dict]) -> _Script:
    label = ERA_LABELS[era]
    opener = (f"Sing, Muse, of the {label} days. You were there, traveler, and Ithaca remembers."
              if path == "odysseus" else
              f"Listen, young one. Before your voyage began, there was the {label} era, and this is why it mattered.")
    body = " ".join(f"{e['title']}. {e['summary']} {e['why_it_matters']}" for e in entries[:3])
    closer = "Now take up the relic of this age, and sail on to the next." if path == "odysseus" else \
             "Now you carry the story too. Collect the relic, and the voyage continues."
    return _Script(title=f"The Song of {label.split('· ')[-1]}", script=f"{opener} {body} {closer}",
                   used_lore_ids=[e["id"] for e in entries[:3]])


async def episode(*, era: str, path: str, topic: Optional[str] = None, voice: bool = True,
                  games: Optional[list[str]] = None, handle: Optional[str] = None) -> EpisodeResponse:
    key = hashlib.sha1(f"{era}|{path}|{(topic or '').strip().lower()}".encode()).hexdigest()[:12]
    hit = _cache.get(key)
    s = get_settings()
    stale = hit and hit.generated_by == "template" and s.has_gemini
    if hit and not stale and (hit.audio_url or not voice or not s.has_elevenlabs):
        return hit.model_copy(update={"cached": True})

    L = lore()
    entries = await L.search(topic, era=era, k=4) if topic else L.for_era(era)[:4]
    if not entries:
        entries = await L.search(topic or era, k=3)

    lore_block = json.dumps([{k: e.get(k) for k in ("id", "era", "year", "title", "people", "summary", "why_it_matters")}
                             for e in entries], indent=1)
    who = f"Listener handle: {handle}. " if handle else ""
    plays = f"They currently play: {', '.join(games)}. " if games else ""
    prompt = (f"path={path}\nera={ERA_LABELS[era]}\n{who}{plays}\n"
              f"{'Focus: ' + topic if topic else 'Sing the story of this era.'}\n\nLORE:\n{lore_block}")
    gen = await gemini.generate_json(prompt, _Script, system=BARD_SYSTEM, timeout=get_settings().bard_timeout_s)
    by = "gemini"
    if gen is None or not gen.script.strip():
        gen, by = _template(era, path, entries), "template"

    used = [e for e in entries if e["id"] in set(gen.used_lore_ids)] or entries[:3]
    audio = await tts.narrate(gen.script) if voice else None
    ep = EpisodeResponse(
        episode_id=f"ep_{key}",
        era=era, path=path, title=gen.title, script=gen.script, audio_url=audio,
        cues=[VideoCue(video_id=e.get("video_id"), start_s=e.get("start_s") or 0, end_s=e.get("end_s"),
                       title=e["title"], lore_id=e["id"]) for e in used],
        sources=[e["id"] for e in used], cached=False, generated_by=by,
    )
    if by == "gemini" or not get_settings().has_gemini:
        _cache[key] = ep
        _save_cache()
    return ep

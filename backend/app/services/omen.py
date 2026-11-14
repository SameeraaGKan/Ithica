"""Daily Omen (P1): one lore question per day, sent over iMessage by B, answered by text.
Deterministic per date so every fan gets the same omen; answers checked by Gemini, fuzzy match as fallback."""
import difflib
import hashlib
import re
from datetime import date
from typing import Optional

from pydantic import BaseModel

from app.config import get_settings
from app.schemas import Omen, OmenResult
from app.services import gemini
from app.services.lore import lore
from app.services.store import award, store

REWARD = 50
_answered: set[tuple[str, str]] = set()  # (fan_id, omen_id); memory is fine, events table has the durable record


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def today_omen(d: Optional[date] = None) -> tuple[Omen, dict, list[str]]:
    d = d or date.today()
    entries = sorted(lore().entries, key=lambda e: e["id"])
    e = entries[int(hashlib.sha1(d.isoformat().encode()).hexdigest(), 16) % len(entries)]
    if e.get("people"):
        q = f"In the {e['year']} chapter \"{e['title']}\", name one FaZe member at the heart of the story."
        answers = e["people"]
    else:
        q = f"In what year did this happen: {e['summary']}"
        answers = [str(e["year"])]
    oid = f"omen_{d.isoformat()}"
    hub = get_settings().hub_base_url.rstrip("/")
    text = f"🔮 Today's Omen ({REWARD} Drachmae): {q}\nReply with your answer. {hub}"
    return Omen(date=d.isoformat(), omen_id=oid, question=q, reward=REWARD, lore_id=e["id"], imessage_text=text), e, answers


class _Judge(BaseModel):
    correct: bool


async def answer(fan_id: str, text: str) -> OmenResult:
    omen, e, answers = today_omen()
    if (fan_id, omen.omen_id) in _answered:
        return OmenResult(correct=True, reply="You already read today's omen. Return tomorrow.", drachmae_awarded=0, already_answered=True)
    guess = _norm(text)
    correct = any(_norm(a) in guess or difflib.SequenceMatcher(None, _norm(a), guess).ratio() > 0.8 for a in answers)
    if not correct:
        j = await gemini.generate_json(
            f"Question: {omen.question}\nAccepted answers: {answers}\nFan's answer: {text}\nIs the fan's answer correct "
            f"(allow nicknames, 'FaZe ' prefixes, typos)?", _Judge, timeout=4, temperature=0)
        correct = bool(j and j.correct)
    st = store()
    await st.upsert_fan(fan_id)
    if correct:
        _answered.add((fan_id, omen.omen_id))
        await award(fan_id, "omen", "imessage", {"omen_id": omen.omen_id, "correct": True}, drachmae=REWARD)
        reply = f"The omen is true. +{REWARD} Drachmae. {e['why_it_matters']}"
    else:
        await st.log_event(fan_id, "omen", "imessage", {"omen_id": omen.omen_id, "correct": False})
        reply = f"Not quite, traveler. The answer was {answers[0]}. {e['title']}: {e['summary']}"
        _answered.add((fan_id, omen.omen_id))
    return OmenResult(correct=correct, reply=reply, drachmae_awarded=REWARD if correct else 0)

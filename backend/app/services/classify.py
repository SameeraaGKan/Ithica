"""Odysseus (returning) vs Telemachus (new) + entry era."""
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.schemas import ERA_LABELS, ClassifyRequest
from app.services import gemini

MEMBER_ERA = {
    "clipz": "2010_trickshots", "housecat": "2010_trickshots", "resistance": "2010_trickshots", "apex": "2010_trickshots",
    "rug": "2013_rug_era", "banks": "2013_rug_era", "adapt": "2013_rug_era", "jarvis": "2013_rug_era",
    "swagg": "2020_nuke_squad", "booya": "2020_nuke_squad", "nickmercs": "2020_nuke_squad",
    "snoop": "2022_snoop", "snoop dogg": "2022_snoop",
    "lacy": "today", "kaysan": "today", "stable ronaldo": "today", "silky": "today", "jason": "today",
}


def era_for_year(y: int) -> str:
    if y <= 2012:
        return "2010_trickshots"
    if y <= 2018:
        return "2013_rug_era"
    if y <= 2021:
        return "2020_nuke_squad"
    if y <= 2023:
        return "2022_snoop"
    return "today"


class _LLM(BaseModel):
    path: Literal["odysseus", "telemachus"]
    entry_era: Literal["2010_trickshots", "2013_rug_era", "2020_nuke_squad", "2022_snoop", "today"]
    first_found_year: Optional[int] = None
    favorite_member: Optional[str] = None
    games: list[str] = Field(default_factory=list)
    reason: str


def _rule_based(year: Optional[int], member: Optional[str], games: list[str]) -> tuple[str, str, str]:
    m_era = MEMBER_ERA.get((member or "").strip().lower().replace("faze ", ""))
    if year:
        era = era_for_year(year)
        path = "odysseus" if year <= 2021 else "telemachus"
        return path, era, f"found FaZe around {year}"
    if m_era:
        return ("telemachus" if m_era == "today" else "odysseus"), m_era, f"their guy is {member}"
    return "telemachus", "today", "new to FaZe"


async def classify(req: ClassifyRequest) -> tuple[str, str, list[str], str]:
    year, member, games = req.first_found_year, req.favorite_member, list(req.games)
    if req.transcript and not (year or member):
        res = await gemini.generate_json(
            "Classify this FaZe fan from their onboarding conversation. odysseus = found FaZe before 2022 and drifted away "
            "or is returning; telemachus = new or recent fan. entry_era = when they first found FaZe "
            "(2010_trickshots <=2012, 2013_rug_era 2013-2018, 2020_nuke_squad 2019-2021, 2022_snoop 2022-2023, today 2024+).\n\n"
            f"TRANSCRIPT:\n{req.transcript}", _LLM, timeout=6, temperature=0.1)
        if res:
            return res.path, res.entry_era, res.games or games, res.reason
        m = re.search(r"\b(20[01]\d|202\d)\b", req.transcript)
        year = int(m.group(1)) if m else None
        member = next((k for k in MEMBER_ERA if k in req.transcript.lower()), None)
    path, era, reason = _rule_based(year, member, games)
    return path, era, games, reason


def bard_line(path: str, era: str, handle: Optional[str]) -> str:
    name = handle or "traveler"
    if path == "odysseus":
        return f"Welcome home, {name}. You sailed with FaZe in the {ERA_LABELS[era]} days. Ithaca remembers you."
    return f"Welcome, {name}. Like Telemachus, you've come looking for the legend. Let me sing you the story you missed."

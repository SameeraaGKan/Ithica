"""Request/response contracts. Share these with B (agent tools), C (hub), D (extension)."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

Path_ = Literal["odysseus", "telemachus"]
Era = Literal["2010_trickshots", "2013_rug_era", "2020_nuke_squad", "2022_snoop", "today"]
ERAS: list[str] = ["2010_trickshots", "2013_rug_era", "2020_nuke_squad", "2022_snoop", "today"]
ERA_LABELS = {
    "2010_trickshots": "2010 · Trickshots",
    "2013_rug_era": "2013 · Rug Era",
    "2020_nuke_squad": "2020 · Nuke Squad",
    "2022_snoop": "2022 · Snoop",
    "today": "Today",
}


# ---------- onboarding ----------
class ClassifyRequest(BaseModel):
    fan_id: Optional[str] = None
    handle: Optional[str] = None
    phone: Optional[str] = None
    # either structured answers from the agent tool call...
    first_found_year: Optional[int] = None
    favorite_member: Optional[str] = None
    games: list[str] = Field(default_factory=list)
    # ...or the raw transcript and we classify it with Gemini
    transcript: Optional[str] = None


class ClassifyResponse(BaseModel):
    fan_id: str
    path: Path_
    entry_era: Era
    games: list[str]
    reason: str
    bard_line: str  # something the agent can say straight back


# ---------- odyssey map ----------
class EraNode(BaseModel):
    era: Era
    label: str
    is_entry: bool
    unlocked: bool
    relics_collected: int
    relics_total: int


class RelicOut(BaseModel):
    id: str
    era: Era
    name: str
    rarity: str
    art_url: Optional[str] = None
    earned_at: Optional[str] = None
    via: Optional[str] = None


class OdysseyResponse(BaseModel):
    fan_id: str
    handle: Optional[str]
    path: Optional[Path_]
    entry_era: Optional[Era]
    drachmae: int
    map: list[EraNode]
    relics: list[RelicOut]
    next_episode: dict


# ---------- bard ----------
class EpisodeRequest(BaseModel):
    fan_id: Optional[str] = None
    era: Optional[Era] = None
    path: Optional[Path_] = None
    topic: Optional[str] = None  # free text, e.g. "why Swagg matters"
    voice: bool = True


class VideoCue(BaseModel):
    video_id: Optional[str]
    start_s: int = 0
    end_s: Optional[int] = None
    title: str
    lore_id: str


class EpisodeResponse(BaseModel):
    episode_id: str
    era: Era
    path: Path_
    title: str
    script: str
    audio_url: Optional[str]
    cues: list[VideoCue]
    sources: list[str]
    cached: bool
    generated_by: Literal["gemini", "template"]


# ---------- oracle ----------
class OracleVerdict(BaseModel):
    mode: Literal["argos", "bow_trial"]
    recognized: bool
    era: Optional[Era] = None
    confidence: float = 0.0
    score: Optional[int] = None  # bow_trial 0-100
    reasons: list[str] = Field(default_factory=list)
    spoken: str  # what the Oracle says out loud
    relic: Optional[RelicOut] = None
    drachmae_awarded: int = 0
    fallback: bool = False
    latency_ms: int = 0


# ---------- siren ----------
class SirenContext(BaseModel):
    video_id: str
    t: int
    is_faze: bool
    lore: Optional[dict]
    relic_available: Optional[RelicOut]


class CollectRequest(BaseModel):
    fan_id: str
    video_id: str
    t: int = 0
    lore_id: Optional[str] = None


class CollectResponse(BaseModel):
    relic: Optional[RelicOut]
    drachmae_awarded: int
    drachmae_total: int
    already_had: bool

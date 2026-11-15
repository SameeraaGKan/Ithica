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
    fan_token: str  # send as Authorization: Bearer <fan_token>
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
    has_pass: bool = False
    games: list[str] = Field(default_factory=list)
    map: list[EraNode]
    relics: list[RelicOut]
    locked_relics: list[RelicOut] = Field(default_factory=list)
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
    url: Optional[str] = None  # YouTube: the exact moment when video_id is set, otherwise a search for it


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
    # argos merch read-out
    item: Optional[str] = None       # what the fan is showing, e.g. "grey FaZe hoodie"
    year: Optional[int] = None       # best estimate of when it was made
    era_reason: Optional[str] = None  # the clue that decided the era
    # bow trial extras
    trial_id: Optional[str] = None
    sponsor: Optional[str] = None
    rank: Optional[int] = None
    # for B: iMessage follow-up (Chert) after the call
    imessage_text: Optional[str] = None
    share_url: Optional[str] = None


# ---------- siren ----------
class SirenContext(BaseModel):
    video_id: str
    t: int
    is_faze: bool
    lore: Optional[dict]
    relic_available: Optional[RelicOut]
    transcript: Optional[str] = None  # what's being said around t, if we have the transcript
    next_relic: Optional[RelicOut] = None  # the next relic this fan hasn't collected (needs fan_id)


class CollectRequest(BaseModel):
    fan_id: str
    video_id: str = "web"          # extension sends the YouTube id; the Hub may omit it
    t: int = 0
    lore_id: Optional[str] = None
    relic_id: Optional[str] = None  # Hub: claim a specific relic; omitted on web = next uncollected


class CollectResponse(BaseModel):
    relic: Optional[RelicOut]
    drachmae_awarded: int
    drachmae_total: int
    already_had: bool


# ---------- ask the bard ----------
class AskRequest(BaseModel):
    question: str
    fan_id: Optional[str] = None
    video_id: Optional[str] = None
    t: Optional[int] = None
    voice: bool = True


class AskResponse(BaseModel):
    answer: str
    audio_url: Optional[str]
    lore_ids: list[str]
    generated_by: Literal["gemini", "template"]


# ---------- daily omen ----------
class Omen(BaseModel):
    date: str
    omen_id: str
    question: str
    reward: int
    lore_id: str
    imessage_text: str


class OmenAnswer(BaseModel):
    fan_id: str
    answer: str


class OmenResult(BaseModel):
    correct: bool
    reply: str
    drachmae_awarded: int
    already_answered: bool = False

import json
"""The Oracle: give it an image + mode, get a spoken verdict back.
Transport-agnostic on purpose: Chert webhook, Chert tool call, or the web-camera
fallback page all call `judge()` the same way. Frames are never stored."""
import logging
import random
import time
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.config import BASE_DIR, get_settings
from app.schemas import ERA_LABELS, OracleVerdict, RelicOut
from app.services import gemini
from app.services.lore import lore
from app.services.store import award, store

log = logging.getLogger("ithaca.oracle")

# Dates from FaZe's own logo-history page (fazeclan.com/pages/about) and documented collabs.
WHAT_COUNTS = """WHAT COUNTS AS FAZE (any ONE of these is enough):
- The FaZe monogram in ANY version or colour: the angular "F" made of stacked bars/blades (it also reads as F+C).
  It appears in red, black, white, grey, gold, tricolour (red/yellow/blue), outlined, or tone-on-tone.
- The words "FaZe", "FaZe Clan", "FaZe Sniping" or "FaZe Apparel" (note the capital Z), even small, on a tag, sleeve or back print.
- A FaZe co-branded collab: FaZe x Champion (Champion "C" logo next to or blended with FaZe), Kappa, Manchester City,
  Takashi Murakami (rainbow flowers jersey or mousepad), NFL, Lyrical Lemonade, Anti Social Social Club, Warren Lotas,
  BE@RBRICK, CLOT, LA Kings, NASCAR, OpTic, G-Shock, Puma.
- A FaZe esports jersey (player name or number with FaZe branding and sponsor patches), or an Atlanta FaZe (Call of Duty League) item.
- FaZe content on a screen: a FaZe YouTube channel or video, a FaZe stream overlay, a FaZe member's channel.
- Merch for a FaZe member that says FaZe (e.g. "FaZe Rug", "FaZe Banks", "FaZe Apex", "FaZe Swagg", "FaZe Jarvis").
NOT FaZe: other esports orgs (OpTic alone, 100 Thieves, Sentinels, TSM, NRG, Team Liquid, Cloud9), generic gaming gear,
school or club hoodies, random red logos, people's faces. Never claim a logo you cannot actually see."""

MERCH_REF_PATH = BASE_DIR / "data" / "merch_reference.json"


def merch_reference_text() -> str:
    """Verified merch per era, from data/merch_reference.json. Empty when the team hasn't filled it in."""
    try:
        ref = json.loads(MERCH_REF_PATH.read_text())
    except (OSError, ValueError):
        return ""
    lines = []
    for era, body in ref.items():
        if era.startswith("_"):
            continue
        for it in (body or {}).get("items", []):
            lines.append(f"- {era}: {it.get('name', '?')} ({it.get('year', '?')}), clue: {it.get('clue', '?')}")
    return "KNOWN FAZE MERCH (verified; date against these first):\n" + "\n".join(lines) if lines else ""


ERA_GUIDE = """HOW TO DATE IT (use the strongest clue; say which one decided it in items_seen):
FaZe logo versions (official dates):
- 1st logo, May 2010 to Jan 2016: the original FaZe Sniping / FaZe Clan mark. The earliest "FAZE SNIPING" was a blocky,
  metallic, 3D-style wordmark. The early monogram is sharp and often tricolour.
- 3rd logo, Mar 2016 to Aug 2018: the tricolour monogram reworked, slightly cleaner, some angles rounded (FaZe House era).
- 4th logo, Aug 2018 to Jun 2022: refined monogram of the competitive / esports era.
- 5th logo, Jun 2022 to Dec 2024: modernised mark. FaZe lettering beside the monogram dates from about 2021 onward.
- 7th logo, Jan 2025 on: smoother edges with inner curved points, usually no lettering. 2025 also introduced "FaZe Camo" prints.
Map to the five eras of the Odyssey:
- 2010_trickshots (2010-2012): FaZe Sniping wordmark, the earliest sharp monogram, Call of Duty MW2 / MW3 / Black Ops 1
  trickshot montage on screen, budget screen-printed tees, an Xbox 360 era setup.
- 2013_rug_era (2013-2018): the tricolour monogram on simple hoodies and tees (the classic grey or black hoodie with a big
  chest "F"), vlog-era member merch (FaZe Rug, Banks, Adapt, Jarvis), Black Ops 2 / Ghosts / Advanced Warfare / Black Ops 3
  on screen, early esports gear.
- 2020_nuke_squad (2019-2021): streetwear collabs, especially FaZe x Champion (2018-2019, including "GHOST" and "BLACK OPS"
  hoodies and a hockey jersey), Kappa (2019), Manchester City, G-Shock, Murakami (2021), Fortnite or Warzone on screen,
  streaming setups, the refined 2018 monogram.
- 2022_snoop (2022-2023): Snoop Dogg / FaZe items, NFL and NASCAR-style collabs, the modernised 2022 logo with lettering,
  public-company era merch.
- today (2024 on): the smoothed 2025 logo, FaZe Camo, newest creator merch.
If the only clue is a plain monogram with no other context, pick the era its logo version fits and keep confidence at or
below 0.55. Do NOT default to one era: decide from what you see, and do not choose 2013_rug_era unless the clues fit it."""


class _Argos(BaseModel):
    item: str = Field(description="What the fan is holding up or showing, in a few words (e.g. 'grey hoodie', 'jersey', 'phone screen')")
    faze_clues: list[str] = Field(description="Every FaZe clue actually visible: logo version and colour, words, collab "
                                              "co-brand, jersey details, game on screen. Empty if none.")
    faze_related: bool = Field(description="True only if at least one clue from WHAT COUNTS AS FAZE is visible")
    era: Literal["2010_trickshots", "2013_rug_era", "2020_nuke_squad", "2022_snoop", "today"]
    era_reason: str = Field(description="The single clue that decided the era, in one short phrase")
    confidence: float = Field(ge=0, le=1)
    items_seen: list[str] = Field(description="Short list of what you see that informed the call")
    year: Optional[int] = Field(default=None, description="Best estimate of the year this item was made, e.g. 2014. Null if unsure.")
    spoken: str = Field(description="1-2 sentences the Oracle says aloud, Homeric and warm, under 35 words")


class _Bow(BaseModel):
    is_trickshot: bool = Field(description="Does the frame show a trickshot / gaming highlight or a real-life trick attempt?")
    safe: bool = Field(description="False if the image contains anything unsafe or inappropriate for a public leaderboard")
    score: int = Field(ge=0, le=100, description="Trickshot quality 0-100: difficulty, style, clarity")
    reasons: list[str] = Field(description="2-3 short reasons for the score")
    spoken: str = Field(description="1-2 sentences the Oracle says aloud, a dramatic judgement, under 35 words")


ORACLE_SYSTEM = ("You are the Oracle of Ithaca (Tiresias), a blind seer who nonetheless sees all, judging fans of FaZe Clan "
                 "over a video call. Be decisive, dramatic, kind. Never mention being an AI or an image. Never claim to know the "
                 "person's identity.")

CANNED_ARGOS = [
    "The mists are thick, but I sense an old soul of FaZe before me. Welcome home, Odysseus. Ithaca kept your place.",
    "Argos lifts his head. He knows you, traveler. The long voyage is over. Welcome home.",
]
CANNED_BOW = [
    "The bow is strung, and the arrow flies true enough. The suitors grow nervous. I name it worthy.",
    "A bold shot, traveler. The gods murmur. Return next week and string the bow again.",
]
BOW_PASS = 70
BOW_RELIC = "r_swagg_bow"


def _imessage(v: OracleVerdict, fan_id: Optional[str]) -> None:
    """Result card text for B to send over iMessage (Chert) after the FaceTime."""
    s = get_settings()
    v.share_url = f"{s.hub_base_url.rstrip('/')}/odyssey/{fan_id}" if fan_id else s.hub_base_url
    lines = ["🏛️ The Oracle has spoken."]
    if v.mode == "argos" and v.era:
        lines.append(f"Era recognized: {ERA_LABELS.get(v.era, v.era)}. Welcome home.")
    if v.mode == "bow_trial" and v.score is not None:
        sponsor = f" (presented by {v.sponsor})" if v.sponsor else ""
        rank = f" · #{v.rank} among the suitors" if v.rank else ""
        lines.append(f"Bow Trial{sponsor}: {v.score}/100{rank}.")
    if v.relic:
        lines.append(f"Relic earned: {v.relic.name} ({v.relic.rarity}).")
    if v.drachmae_awarded:
        lines.append(f"+{v.drachmae_awarded} Drachmae.")
    lines.append(f"Your Odyssey: {v.share_url}")
    v.imessage_text = "\n".join(lines)


def _era_relic(era: str) -> Optional[str]:
    for e in lore().for_era(era):
        if e.get("relic"):
            return e["relic"]["id"]
    return None


async def _ask(prompt: str, schema, **kw):
    """Try each provider in ORACLE_PROVIDERS order; the first one that returns a valid verdict wins."""
    from app.services import local_vision
    for name in get_settings().oracle_providers.split(","):
        name = name.strip()
        call = local_vision.generate_json if name == "ollama" else gemini.generate_json if name == "gemini" else None
        if call is None:
            continue
        res = await call(prompt, schema, **kw)
        if res is not None:
            return res
    return None


async def judge(image: bytes, mime: str, mode: str, *, fan_id: Optional[str] = None, context: str = "",
                source: str = "web") -> OracleVerdict:
    s = get_settings()
    t0 = time.perf_counter()
    fallback = False

    if mode == "argos":
        prompt = (f"Mode: ARGOS REMEMBERS. The fan is showing you something from their FaZe past: merch, a jersey, a "
                  f"poster, a collab piece, their setup, or FaZe content on a screen. Work in this order:\n"
                  f"1. Say what the item is. 2. List every FaZe clue you can actually see (logo version and colour, words, "
                  f"collab co-branding, jersey details, the game on screen). 3. Decide faze_related using WHAT COUNTS AS FAZE. "
                  f"4. Date it with HOW TO DATE IT and name the deciding clue. 5. Speak: welcome them home and name the era "
                  f"in words a fan would know (e.g. 'the trickshot days', 'the Rug and Banks vlog years', 'the Champion "
                  f"drops and Warzone nukes', 'the Snoop era', 'the new FaZe'), and mention the item you saw.\n"
                  f"If nothing FaZe is visible: faze_related=false, confidence below 0.2, and the spoken line gently asks, in "
                  f"character, to hold their FaZe relic closer to the light.\n\n{WHAT_COUNTS}\n\n{ERA_GUIDE}\n\n{merch_reference_text()}\n\n"
                  f"Extra context: {context or 'none'}")
        res = await _ask(prompt, _Argos, images=[(image, mime)], system=ORACLE_SYSTEM,
                                         timeout=s.oracle_timeout_s, temperature=0.0)
        if res is None:
            fallback = True
            res = _Argos(item="", faze_clues=[], faze_related=True, era="2013_rug_era", era_reason="", confidence=0.0,
                         items_seen=[], spoken=random.choice(CANNED_ARGOS))
        recognized = res.faze_related and res.confidence >= 0.35
        if res.faze_related and not fallback and res.confidence < 0.35:
            res.spoken += " The vision is faint. Hold it closer to the light."
        reasons = ([f"Item: {res.item}"] if res.item else []) + list(res.faze_clues or res.items_seen) + \
                  ([f"Era clue: {res.era_reason}"] if res.era_reason else [])
        v = OracleVerdict(mode="argos", recognized=recognized or fallback, era=res.era, confidence=res.confidence,
                          reasons=reasons, spoken=res.spoken, fallback=fallback,
                          item=res.item or None, year=res.year, era_reason=res.era_reason or None)
        relic_id = _era_relic(res.era) if v.recognized else None
        event, drach = "oracle_argos", 40
    else:
        prompt = ("Mode: THE BOW TRIAL. Only the true king can string the bow of Odysseus. The fan is showing a trickshot "
                  "(a clip on their screen or a live attempt). Judge it like FaZe recruiters judging a trickshot montage.\n"
                  f"Extra context: {context or 'none'}")
        res = await _ask(prompt, _Bow, images=[(image, mime)], system=ORACLE_SYSTEM,
                                         timeout=s.oracle_timeout_s, temperature=0.5)
        if res is None:
            fallback = True
            res = _Bow(is_trickshot=True, safe=True, score=random.randint(72, 88), reasons=["The Oracle's sight was clouded; a scripted verdict was given."],
                       spoken=random.choice(CANNED_BOW))
        if not res.safe:
            res.score, res.spoken = 0, "The Oracle will not judge this offering. Bring a worthier shot."
        v = OracleVerdict(mode="bow_trial", recognized=res.is_trickshot and res.safe, score=res.score,
                          confidence=1.0 if not fallback else 0.0, reasons=res.reasons, spoken=res.spoken, fallback=fallback)
        relic_id = BOW_RELIC if v.recognized and res.score >= BOW_PASS else None
        event, drach = "trial_entry", 50 if v.recognized else 0
        trial = await store().current_trial()
        v.trial_id, v.sponsor = trial["id"], trial.get("sponsor")

    if fan_id:
        st = store()
        if relic_id:
            relic, already = await st.grant_relic(fan_id, relic_id, via=source)
            if relic:
                v.relic = RelicOut(**{k: relic.get(k) for k in RelicOut.model_fields})
                if not already:
                    await st.log_event(fan_id, "relic", source, {"era": relic["era"], "relic_id": relic_id})
                    drach += 25
        await award(fan_id, event, source, {"mode": mode, "era": v.era, "score": v.score, "fallback": fallback,
                                            "trial_id": v.trial_id, "sponsor": v.sponsor}, drachmae=drach)
        v.drachmae_awarded = drach
        if mode == "argos" and v.era:
            await st.update_fan(fan_id, entry_era=(await st.get_fan(fan_id) or {}).get("entry_era") or v.era)
        # fallback verdicts skip the Gemini safety check, so they never go on the public leaderboard
        if mode == "bow_trial" and v.recognized and not fallback:
            await st.add_trial_entry(v.trial_id, fan_id, v.score or 0, v.spoken)
            board = await st.leaderboard(v.trial_id, limit=100)
            v.rank = next((r["rank"] for r in board if r["fan_id"] == fan_id), None)
            if v.sponsor:
                await st.log_event(fan_id, "sponsored_impression", source, {"sponsor": v.sponsor, "trial_id": v.trial_id})
    _imessage(v, fan_id)

    v.latency_ms = int((time.perf_counter() - t0) * 1000)
    return v

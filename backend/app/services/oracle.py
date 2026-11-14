"""The Oracle: give it an image + mode, get a spoken verdict back.
Transport-agnostic on purpose: Chert webhook, Chert tool call, or the web-camera
fallback page all call `judge()` the same way. Frames are never stored."""
import logging
import random
import time
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.config import get_settings
from app.schemas import ERA_LABELS, OracleVerdict, RelicOut
from app.services import gemini
from app.services.lore import lore
from app.services.store import award, store

log = logging.getLogger("ithaca.oracle")

ERA_GUIDE = """FaZe eras (pick the closest):
- 2010_trickshots: early FaZe Sniping / Call of Duty MW2-MW3-BO trickshot days, montage-era logos, early red/black FaZe "F" logo.
- 2013_rug_era: vlog era, early merch hoodies, Rug/Banks/Apex house-era content, esports beginnings.
- 2020_nuke_squad: Warzone era, streaming setups, Swagg-era merch.
- 2022_snoop: Snoop Dogg collab, public-company era, collab drops.
- today: current FaZe branding and creators.
If you cannot tell the era, choose the most plausible and lower your confidence."""


class _Argos(BaseModel):
    faze_related: bool = Field(description="Is there FaZe merch, logo, poster, or FaZe-related item in view?")
    era: Literal["2010_trickshots", "2013_rug_era", "2020_nuke_squad", "2022_snoop", "today"]
    confidence: float = Field(ge=0, le=1)
    items_seen: list[str] = Field(description="Short list of what you see that informed the call")
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


async def judge(image: bytes, mime: str, mode: str, *, fan_id: Optional[str] = None, context: str = "",
                source: str = "web") -> OracleVerdict:
    s = get_settings()
    t0 = time.perf_counter()
    fallback = False

    if mode == "argos":
        prompt = (f"Mode: ARGOS REMEMBERS. The fan is showing you something from their FaZe past (merch, a poster, their setup). "
                  f"Identify the FaZe era it comes from and welcome them home by naming that era.\n"
                  f"BE STRICT: faze_related is true ONLY if a FaZe logo (the stylized red 'F' / FaZe wordmark) or clearly FaZe "
                  f"merchandise is actually visible. Other hoodies, logos, people, rooms or screens are NOT FaZe. If nothing FaZe is "
                  f"visible, set faze_related=false, confidence below 0.2, and make the spoken line a gentle, in-character request to "
                  f"hold their FaZe relic up to the light. Never pretend to see a logo that isn't there.\n{ERA_GUIDE}\n"
                  f"Extra context: {context or 'none'}")
        res = await gemini.generate_json(prompt, _Argos, images=[(image, mime)], system=ORACLE_SYSTEM,
                                         timeout=s.oracle_timeout_s, temperature=0.4)
        if res is None:
            fallback = True
            res = _Argos(faze_related=True, era="2013_rug_era", confidence=0.0, items_seen=[], spoken=random.choice(CANNED_ARGOS))
        recognized = res.faze_related and res.confidence >= 0.35
        if res.faze_related and not fallback and res.confidence < 0.35:
            res.spoken += " The vision is faint. Hold it closer to the light."
        v = OracleVerdict(mode="argos", recognized=recognized or fallback, era=res.era, confidence=res.confidence,
                          reasons=res.items_seen, spoken=res.spoken, fallback=fallback)
        relic_id = _era_relic(res.era) if v.recognized else None
        event, drach = "oracle_argos", 40
    else:
        prompt = ("Mode: THE BOW TRIAL. Only the true king can string the bow of Odysseus. The fan is showing a trickshot "
                  "(a clip on their screen or a live attempt). Judge it like FaZe recruiters judging a trickshot montage.\n"
                  f"Extra context: {context or 'none'}")
        res = await gemini.generate_json(prompt, _Bow, images=[(image, mime)], system=ORACLE_SYSTEM,
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
        if mode == "bow_trial" and v.recognized:
            await st.add_trial_entry(v.trial_id, fan_id, v.score or 0, v.spoken)
            board = await st.leaderboard(v.trial_id, limit=100)
            v.rank = next((r["rank"] for r in board if r["fan_id"] == fan_id), None)
            if v.sponsor:
                await st.log_event(fan_id, "sponsored_impression", source, {"sponsor": v.sponsor, "trial_id": v.trial_id})
    _imessage(v, fan_id)

    v.latency_ms = int((time.perf_counter() - t0) * 1000)
    return v

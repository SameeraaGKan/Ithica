"""The whole API surface from the plan, plus ElevenLabs agent tool aliases."""
import base64
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from app.auth import check_fan, fan_token, require_service_key

from app.schemas import (ERA_LABELS, ERAS, AskRequest, AskResponse, Omen, OmenAnswer, OmenResult, ClassifyRequest, ClassifyResponse, CollectRequest, CollectResponse,
                         EpisodeRequest, EpisodeResponse, EraNode, OdysseyResponse, OracleVerdict, RelicOut,
                         SirenContext)
from app.services import bard, omen, oracle
from app.services.classify import bard_line, classify
from app.services.lore import lore
from app.services.store import PRICES, award, relic_catalog, store

log = logging.getLogger("ithaca.api")
router = APIRouter()


def _relic_out(r: Optional[dict]) -> Optional[RelicOut]:
    return RelicOut(**{k: r.get(k) for k in RelicOut.model_fields}) if r else None


# ------------------------------------------------------------- onboarding
@router.post("/onboard/classify", response_model=ClassifyResponse, tags=["onboarding"])
async def onboard_classify(req: ClassifyRequest):
    st = store()
    fan = await st.upsert_fan(req.fan_id, req.handle, req.phone)
    path, era, games, reason = await classify(req)
    await st.update_fan(fan["id"], path=path, entry_era=era, games=games or None)
    await award(fan["id"], "onboard", "web", {"path": path, "era": era})
    return ClassifyResponse(fan_id=fan["id"], fan_token=fan_token(fan["id"]), path=path, entry_era=era, games=games, reason=reason,
                            bard_line=bard_line(path, era, fan.get("handle")))


# ------------------------------------------------------------- odyssey map
@router.get("/odyssey/{fan_id}", response_model=OdysseyResponse, tags=["hub"])
async def odyssey(fan_id: str):
    st = store()
    fan = await st.get_fan(fan_id)
    if not fan:
        raise HTTPException(404, "unknown fan")
    mine = await st.list_fan_relics(fan_id)
    have = {r["id"] for r in mine}
    cat = relic_catalog().values()
    entry = fan.get("entry_era")
    entry_i = ERAS.index(entry) if entry in ERAS else len(ERAS) - 1
    nodes = []
    for i, era in enumerate(ERAS):
        in_era = [r for r in cat if r["era"] == era]
        nodes.append(EraNode(era=era, label=ERA_LABELS[era], is_entry=era == entry,
                             unlocked=fan.get("path") != "odysseus" or i >= entry_i or any(r["id"] in have for r in in_era),
                             relics_collected=sum(r["id"] in have for r in in_era), relics_total=len(in_era)))
    # next episode: first era (from entry outward) with uncollected relics
    order = ERAS[entry_i:] + ERAS[:entry_i] if fan.get("path") == "odysseus" else ERAS
    next_era = next((n.era for n in sorted(nodes, key=lambda n: order.index(n.era)) if n.relics_collected < n.relics_total), entry or "today")
    return OdysseyResponse(fan_id=fan_id, handle=fan.get("handle"), path=fan.get("path"), entry_era=entry,
                           drachmae=fan.get("drachmae", 0), has_pass=bool(fan.get("has_pass")), map=nodes, relics=[_relic_out(r) for r in mine],
                           next_episode={"era": next_era, "path": fan.get("path") or "telemachus", "label": ERA_LABELS[next_era]})


# ------------------------------------------------------------- bard
@router.post("/bard/episode", response_model=EpisodeResponse, tags=["bard"])
async def bard_episode(req: EpisodeRequest):
    fan = await store().get_fan(req.fan_id) if req.fan_id else None
    path = req.path or (fan or {}).get("path") or "telemachus"
    era = req.era or (fan or {}).get("entry_era") or ("today" if path == "telemachus" else "2010_trickshots")
    ep = await bard.episode(era=era, path=path, topic=req.topic, voice=req.voice,
                            games=(fan or {}).get("games"), handle=(fan or {}).get("handle"))
    if req.fan_id:
        await award(req.fan_id, "episode_play", "web", {"episode_id": ep.episode_id, "era": era})
    return ep


# ------------------------------------------------------------- oracle
_DATAURL = re.compile(r"^data:(image/[\w.+-]+);base64,(.*)$", re.S)


async def _read_frame(request: Request) -> tuple[bytes, str, dict]:
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("multipart/"):
        form = await request.form()
        f = form.get("image") or form.get("frame")
        if f is None or not hasattr(f, "read"):
            raise HTTPException(422, "multipart field 'image' required")
        data = await f.read()
        fields = {k: v for k, v in form.items() if isinstance(v, str)}
        return data, f.content_type or "image/jpeg", fields
    body = await request.json()
    raw = body.get("image_b64") or body.get("image") or ""
    m = _DATAURL.match(raw)
    mime = m.group(1) if m else body.get("mime", "image/jpeg")
    try:
        data = base64.b64decode(m.group(2) if m else raw)
    except Exception:
        raise HTTPException(422, "image_b64 must be base64 or a data URL")
    return data, mime, body


@router.post("/oracle/frame", response_model=OracleVerdict, tags=["oracle"],
             description="multipart (image file + mode + fan_id) or JSON {image_b64, mode, fan_id, context, source}. "
                         "mode = argos | bow_trial. Frames are processed in memory and discarded.")
async def oracle_frame(request: Request):
    data, mime, f = await _read_frame(request)
    check_fan(f.get("fan_id") or None, request.headers.get("authorization"))
    if not data:
        raise HTTPException(422, "empty image")
    mode = f.get("mode", "argos")
    if mode not in ("argos", "bow_trial"):
        raise HTTPException(422, "mode must be argos or bow_trial")
    return await oracle.judge(data, mime, mode, fan_id=f.get("fan_id") or None, context=f.get("context", ""),
                              source=f.get("source", "web"))


# ------------------------------------------------------------- chert (B wires the exact payload)
@router.post("/chert/webhook", tags=["chert"], dependencies=[Depends(require_service_key)])
async def chert_webhook(request: Request):
    """Placeholder until we see Chert's real payload. If it carries an image + mode, we judge it
    and return `say` text. B: adapt the field names here once Chert docs are in hand."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    log.info("chert webhook: keys=%s", list(body.keys()))
    img = body.get("image_b64") or body.get("frame")
    if img:
        m = _DATAURL.match(img)
        data = base64.b64decode(m.group(2) if m else img)
        fan = await store().upsert_fan(body.get("fan_id"), phone=body.get("from") or body.get("phone"))
        v = await oracle.judge(data, m.group(1) if m else "image/jpeg", body.get("mode", "argos"),
                               fan_id=fan["id"], source="facetime")
        return {"say": v.spoken, "verdict": v.model_dump(), "fan_id": fan["id"]}
    return {"ok": True}


# ------------------------------------------------------------- siren (extension)
def _lore_for(video_id: str, t: int, channel: Optional[str]) -> tuple[bool, Optional[dict]]:
    """Deterministic: same video always maps to the same lore, so context and collect agree."""
    import zlib
    L = lore()
    e = L.at_timestamp(video_id, t)
    meta = L.video_meta(video_id)
    is_faze = bool(e or meta or (channel and any(c.lower() in channel.lower() for c in ["faze"] + L.faze_channels)))
    if not e and is_faze:
        pool = L.for_era(meta["era"]) if meta and meta.get("era") else []
        pool = pool or sorted(L.entries, key=lambda x: x["id"])
        e = pool[zlib.crc32(video_id.encode()) % len(pool)]
    return is_faze, e


@router.get("/siren/context", response_model=SirenContext, tags=["siren"])
async def siren_context(videoId: str = Query(...), t: int = 0, channel: Optional[str] = None):
    is_faze, e = _lore_for(videoId, t, channel)
    lore_out = {k: e.get(k) for k in ("id", "era", "year", "title", "people", "summary", "why_it_matters", "start_s", "end_s")} if e else None
    if lore_out:
        lore_out["era_label"] = ERA_LABELS.get(e["era"])
    relic = relic_catalog().get(e["relic"]["id"]) if e and e.get("relic") else None
    return SirenContext(video_id=videoId, t=t, is_faze=is_faze, lore=lore_out, relic_available=_relic_out(relic))


@router.post("/siren/collect", response_model=CollectResponse, tags=["siren"])
async def siren_collect(req: CollectRequest, authorization: Optional[str] = Header(default=None)):
    check_fan(req.fan_id, authorization)
    L, st = lore(), store()
    e = L.by_id.get(req.lore_id) if req.lore_id else _lore_for(req.video_id, req.t, "faze")[1]
    relic, already = (None, False)
    gained = 0
    if e and e.get("relic"):
        relic, already = await st.grant_relic(req.fan_id, e["relic"]["id"], via="ext")
        if relic and not already:
            await st.log_event(req.fan_id, "relic", "ext", {"era": relic["era"], "relic_id": relic["id"], "video_id": req.video_id})
            gained += 25
    gained += 1
    total = await award(req.fan_id, "watch", "ext", {"video_id": req.video_id, "t": req.t}, drachmae=gained)
    return CollectResponse(relic=_relic_out(relic), drachmae_awarded=gained, drachmae_total=total, already_had=already)


# ------------------------------------------------------------- war room + mocked checkout
@router.get("/warroom/metrics", tags=["warroom"])
async def warroom_metrics(days: int = Query(14, ge=1, le=90)):
    return await store().metrics(days)


@router.post("/pass/checkout", tags=["warroom"], description="Mocked checkout. sku = odyssey_pass | era_drop:<era>")
async def checkout(fan_id: str, sku: str = "odyssey_pass", authorization: Optional[str] = Header(default=None)):
    check_fan(fan_id, authorization)
    base = sku.split(":")[0]
    if base not in PRICES:
        raise HTTPException(422, "unknown sku")
    if base == "odyssey_pass":
        await store().set_pass(fan_id)
    await store().record_purchase(fan_id, sku, PRICES[base])
    await store().log_event(fan_id, "purchase", "web", {"sku": sku})
    return {"ok": True, "sku": sku, "amount_cents": PRICES[base], "mock": True}


# ------------------------------------------------------------- ElevenLabs agent tools (B)
@router.post("/tools/classify_fan", response_model=ClassifyResponse, tags=["agent-tools"], dependencies=[Depends(require_service_key)])
async def tool_classify(req: ClassifyRequest):
    return await onboard_classify(req)


@router.post("/tools/get_lore", tags=["agent-tools"], dependencies=[Depends(require_service_key)])
async def tool_get_lore(payload: dict):
    """Body: {query, era?}. Returns short text the voice agent can read from."""
    hits = await lore().search(payload.get("query") or "FaZe history", era=payload.get("era"), k=3)
    return {"answer": " ".join(f"{h['title']} ({h['year']}): {h['summary']} {h['why_it_matters']}" for h in hits),
            "lore_ids": [h["id"] for h in hits]}


# ------------------------------------------------------------- ask the bard (extension push-to-talk)
@router.post("/bard/ask", response_model=AskResponse, tags=["bard"],
             description="Grounded Q&A. Extension: send the transcribed question + current videoId/t.")
async def bard_ask(req: AskRequest):
    res = await bard.ask(req.question, video_id=req.video_id, t=req.t, voice=req.voice)
    if req.fan_id:
        await store().log_event(req.fan_id, "ask_bard", "ext" if req.video_id else "web", {"q": req.question[:200]})
    return res


# ------------------------------------------------------------- trials + suitors leaderboard
@router.get("/trials/current", tags=["trials"])
async def trials_current():
    t = await store().current_trial()
    return {**t, "pass_score": oracle.BOW_PASS, "relic_id": oracle.BOW_RELIC}


@router.get("/trials/leaderboard", tags=["trials"])
async def trials_leaderboard(trial_id: Optional[str] = None, limit: int = Query(10, ge=1, le=100)):
    t = await store().current_trial()
    tid = trial_id or t["id"]
    return {"trial_id": tid, "sponsor": t.get("sponsor") if tid == t["id"] else None,
            "suitors": await store().leaderboard(tid, limit)}


@router.post("/trials/current", tags=["trials"], dependencies=[Depends(require_service_key)],
             description="Admin: set this week's sponsor and prompt (the Sponsored Trials revenue line).")
async def trials_set(sponsor: Optional[str] = None, prompt: Optional[str] = None):
    t = await store().set_trial(sponsor, prompt)
    if sponsor:
        await store().record_purchase(None, f"sponsored_trial:{sponsor}", PRICES["sponsored_trial"])
    return t


# ------------------------------------------------------------- daily omen (P1, iMessage via B)
@router.get("/omen/today", response_model=Omen, tags=["omen"])
async def omen_today():
    return omen.today_omen()[0]


@router.post("/omen/answer", response_model=OmenResult, tags=["omen"])
async def omen_answer(req: OmenAnswer, authorization: Optional[str] = Header(default=None)):
    check_fan(req.fan_id, authorization)
    return await omen.answer(req.fan_id, req.answer)

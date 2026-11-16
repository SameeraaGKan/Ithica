"""The whole API surface from the plan, plus ElevenLabs agent tool aliases."""
import base64
import logging
import re
from typing import Optional

from pydantic import BaseModel
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request

from app.auth import check_fan, fan_token, require_service_key

from app.schemas import (ERA_LABELS, ERAS, AskRequest, AskResponse, Omen, OmenAnswer, OmenResult, ClassifyRequest, ClassifyResponse, CollectRequest, CollectResponse,
                         EpisodeRequest, EpisodeResponse, EraNode, OdysseyResponse, OracleVerdict, RelicOut,
                         SirenContext)
from app.services import bard, chert, omen, oracle
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
                           drachmae=fan.get("drachmae", 0), has_pass=bool(fan.get("has_pass")), games=fan.get("games") or [],
                           map=nodes, relics=[_relic_out(r) for r in mine],
                           locked_relics=[_relic_out(r) for r in sorted(cat, key=lambda r: ERAS.index(r["era"])) if r["id"] not in have],
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


@router.delete("/fan/{fan_id}/data", tags=["privacy"],
               description="Erase one fan's data: profile, relics, events, trial entries and purchases.")
async def delete_fan_data(fan_id: str, authorization: Optional[str] = Header(None)):
    check_fan(fan_id, authorization)
    return {"fan_id": fan_id, "deleted": await store().delete_fan_data(fan_id)}


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


# ------------------------------------------------------------- chert (Part B)
@router.post("/chert/webhook", tags=["chert"],
             description="Chert webhook subscription target (event `message.received`). Verifies X-Webhook-Signature "
                         "when CHERT_WEBHOOK_SECRET is set; otherwise falls back to the service key (?key= works).")
async def chert_webhook(request: Request, background: BackgroundTasks):
    import json as _json
    from app.config import get_settings
    s = get_settings()
    raw = await request.body()
    if s.chert_webhook_secret:
        if not chert.verify_signature({k.lower(): v for k, v in request.headers.items()}, raw, s.chert_webhook_secret):
            raise HTTPException(401, "bad Chert signature")
    else:
        await require_service_key(request.headers.get("x-ithaca-key"), request.query_params.get("key"))
    try:
        body = _json.loads(raw or b"{}")
    except Exception:
        raise HTTPException(400, "body must be JSON")
    # legacy direct-frame shape (pre-Chert-docs placeholder) still judged inline
    img = body.get("image_b64") or body.get("frame")
    if img:
        m = _DATAURL.match(img)
        data = base64.b64decode(m.group(2) if m else img)
        fan = await store().upsert_fan(body.get("fan_id"), phone=body.get("from") or body.get("phone"))
        v = await oracle.judge(data, m.group(1) if m else "image/jpeg", body.get("mode", "argos"),
                               fan_id=fan["id"], source="facetime")
        return {"say": v.spoken, "verdict": v.model_dump(), "fan_id": fan["id"]}
    # ack fast; Chert retries slow webhooks. The reply goes out in the background.
    if chert.parse_inbound(body):
        background.add_task(chert.handle_inbound, body)
        return {"ok": True, "queued": True}
    return {"ok": True, "ignored": True}


_ft_sent: set[tuple[str, str]] = set()  # (call_id, mode) -> iMessage card already sent this call


@router.post("/chert/facetime/start", tags=["chert"], dependencies=[Depends(require_service_key)],
             description="Called by oracle_agent when a FaceTime caller joins. {call_id, phone?} -> {fan_id, greeting}.")
async def facetime_start(payload: dict):
    st = store()
    phone = chert.normalize_phone(payload.get("phone"))
    call_id = str(payload.get("call_id") or "call")
    fan = await st.upsert_fan(payload.get("fan_id") or (None if phone else f"ft_{call_id}"[:60]), phone=phone)
    known = bool(fan.get("path") or fan.get("drachmae"))
    await st.log_event(fan["id"], "facetime_call", "facetime", {"call_id": call_id, "known": known})
    name = fan.get("handle") or "traveler"
    greeting = (f"Ah, {name}. The Oracle remembers you. You return to Ithaca." if known else
                "Welcome, traveler. I am the Oracle of Ithaca. I see what others cannot.")
    return {"fan_id": fan["id"], "fan_token": fan_token(fan["id"]), "known": known, "greeting": greeting}


@router.post("/chert/facetime/verdict", tags=["chert"], dependencies=[Depends(require_service_key)],
             description="Called by oracle_agent with a caller video frame. multipart (image + mode + fan_id/phone/call_id) "
                         "or JSON {image_b64, mode, fan_id?, phone?, call_id?}. Returns {say, verdict}; the iMessage "
                         "result card is sent in the background (once per call and mode, only when recognized).")
async def facetime_verdict(request: Request, background: BackgroundTasks):
    data, mime, f = await _read_frame(request)
    if not data:
        raise HTTPException(422, "empty image")
    mode = f.get("mode", "argos")
    if mode not in ("argos", "bow_trial"):
        raise HTTPException(422, "mode must be argos or bow_trial")
    phone = chert.normalize_phone(f.get("phone"))
    call_id = str(f.get("call_id") or "call")
    fan = await store().upsert_fan(f.get("fan_id") or (None if phone else f"ft_{call_id}"[:60]), phone=phone)
    v = await oracle.judge(data, mime, mode, fan_id=fan["id"], context=f.get("context", "Live on FaceTime"), source="facetime")
    imsg = "not_sent"
    if phone and v.recognized and v.imessage_text and (call_id, mode) not in _ft_sent:
        _ft_sent.add((call_id, mode))
        background.add_task(chert.send_imessage, phone, v.imessage_text)
        imsg = "queued"
    return {"say": v.spoken, "fan_id": fan["id"], "imessage": imsg, "verdict": v.model_dump()}


@router.post("/chert/send", tags=["chert"], dependencies=[Depends(require_service_key)],
             description="Admin/test: send one iMessage {phone, body}. Dry-run (logged to /chert/outbox) without CHERT_API_KEY.")
async def chert_send(payload: dict):
    return await chert.send_imessage(payload.get("phone"), payload.get("body") or "")


@router.get("/chert/outbox", tags=["chert"], dependencies=[Depends(require_service_key)],
            description="Last 50 outgoing iMessages (phones masked). Shows dry-run sends when Chert isn't keyed.")
async def chert_outbox():
    return {"live": chert.get_settings().has_chert, "messages": list(chert.outbox)}


# ------------------------------------------------------------- siren (extension)
# FaZe members whose channels don't carry "FaZe" (kept in step with extension/config.js FAZE_MEMBER_NAMES)
FAZE_MEMBER_NAMES = {"rug", "banks", "apex", "adapt", "swagg", "jarvis", "kaysan", "lacy", "stable ronaldo", "silky",
                     "jason", "temperrr", "clipz", "teeqo", "sensei", "censor", "megga", "replays", "nickmercs", "booya",
                     "santana"}


def _is_faze_channel(channel: Optional[str], known: list[str]) -> bool:
    if not channel:
        return False
    c = channel.strip().lower()
    bare = re.sub(r"[^a-z0-9 ]", "", re.sub(r"^faze\s*", "", c)).strip()
    return "faze" in c or bare in FAZE_MEMBER_NAMES or c.lstrip("@") in FAZE_MEMBER_NAMES or \
        any(k.lower() == c for k in known)


def _lore_for(video_id: str, t: int, channel: Optional[str]) -> tuple[bool, Optional[dict]]:
    """Deterministic: same video always maps to the same lore, so context and collect agree."""
    import zlib
    L = lore()
    e = L.at_timestamp(video_id, t)
    meta = L.video_meta(video_id)
    is_faze = bool(e or meta or _is_faze_channel(channel, L.faze_channels))
    if not e and is_faze:
        pool = L.for_era(meta["era"]) if meta and meta.get("era") else []
        pool = [x for x in pool if not x.get("sensitive")] or pool
        pool = pool or sorted([x for x in L.entries if not x.get("sensitive")] or L.entries, key=lambda x: x["id"])
        e = pool[zlib.crc32(video_id.encode()) % len(pool)]
    return is_faze, e


@router.get("/siren/context", response_model=SirenContext, tags=["siren"])
async def siren_context(videoId: str = Query(...), t: int = 0, channel: Optional[str] = None,
                        fan_id: Optional[str] = None):
    is_faze, e = _lore_for(videoId, t, channel)
    lore_out = {k: e.get(k) for k in ("id", "era", "year", "title", "people", "summary", "why_it_matters",
                                      "video_id", "start_s", "end_s")} if e else None
    if lore_out:
        lore_out["era_label"] = ERA_LABELS.get(e["era"])
    relic = relic_catalog().get(e["relic"]["id"]) if e and e.get("relic") else None
    tr = lore().transcript_at(videoId, t) if is_faze else None
    # the next relic this fan hasn't collected yet (shown as a hint in the side panel)
    owned = {r["id"] for r in await store().list_fan_relics(fan_id)} if fan_id else set()
    catalog = relic_catalog()
    nxt = next((catalog[x["relic"]["id"]] for x in lore().entries
                if x.get("relic") and x["relic"]["id"] not in owned and x["relic"]["id"] in catalog), None)
    return SirenContext(video_id=videoId, t=t, is_faze=is_faze, lore=lore_out, relic_available=_relic_out(relic),
                        transcript=tr["text"] if tr else None, next_relic=_relic_out(nxt))


@router.post("/siren/collect", response_model=CollectResponse, tags=["siren"])
async def siren_collect(req: CollectRequest, authorization: Optional[str] = Header(default=None)):
    check_fan(req.fan_id, authorization)
    L, st = lore(), store()
    if req.relic_id:
        e = next((x for x in L.entries if (x.get("relic") or {}).get("id") == req.relic_id), None)
    elif req.lore_id:
        e = L.by_id.get(req.lore_id)
    elif req.video_id == "web":
        # Hub demo button: next relic this fan hasn't got, starting from their entry era
        fan = await st.get_fan(req.fan_id) or {}
        have = {r["id"] for r in await st.list_fan_relics(req.fan_id)}
        start = ERAS.index(fan["entry_era"]) if fan.get("entry_era") in ERAS else 0
        order = ERAS[start:] + ERAS[:start]
        e = next((x for era in order for x in L.for_era(era)
                  if x.get("relic") and x["relic"]["id"] not in have and not x.get("sensitive")), None)
    else:
        e = _lore_for(req.video_id, req.t, "faze")[1]
    if not e:
        # not a FaZe moment in the lore: no relic and no Drachmae, so the endpoint can't be farmed
        fan = await st.get_fan(req.fan_id) or {}
        return CollectResponse(relic=None, drachmae_awarded=0, drachmae_total=fan.get("drachmae", 0), already_had=False)
    relic, already = (None, False)
    gained = 0
    if e.get("relic"):
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
@router.post("/tools/classify_fan", tags=["agent-tools"], dependencies=[Depends(require_service_key)],
             description="Bard agent webhook tool. Same as /onboard/classify, minus fan_token (the LLM doesn't need it; "
                         "the browser got its token from /bard/agent/session).")
async def tool_classify(req: ClassifyRequest):
    res = await onboard_classify(req)
    await store().log_event(res.fan_id, "bard_onboard", "web", {"path": res.path, "era": res.entry_era})
    return res.model_dump(exclude={"fan_token"}) | {"era_label": ERA_LABELS[res.entry_era]}


@router.post("/bard/agent/session", tags=["agent-tools"],
             description="Hub/bard page calls this before starting the voice session. Pre-creates the fan and returns how "
                         "to connect: mode=webrtc (conversation_token), signed (signed_url), public (agent_id) or unconfigured (use the text fallback). "
                         "Pass dynamic_variables to the ElevenLabs SDK's startSession.")
async def bard_agent_session(payload: Optional[dict] = None):
    from app.config import get_settings
    from app.services import bard_agent
    payload = payload or {}
    s = get_settings()
    fan = await store().upsert_fan(payload.get("fan_id"), handle=payload.get("handle"))
    out = {"fan_id": fan["id"], "fan_token": fan_token(fan["id"]),
           "dynamic_variables": {"fan_id": fan["id"], "handle": fan.get("handle") or ""},
           "agent_id": None, "signed_url": None, "conversation_token": None, "mode": "unconfigured"}
    if s.bard_voice != "elevenlabs":
        out["mode"] = "free"  # browser speech + POST /bard/chat
    elif s.has_bard_agent:
        if s.elevenlabs_agent_public:
            out.update(agent_id=s.elevenlabs_agent_id, mode="public")
        # Websocket first: WebRTC (LiveKit) drops on some networks right after connecting, and the SDK's websocket
        # mic already has echo cancellation + noise suppression. WebRTC is only the fallback.
        elif url := await bard_agent.signed_url():
            out.update(agent_id=s.elevenlabs_agent_id, signed_url=url, mode="signed")
        elif token := await bard_agent.conversation_token():
            out.update(agent_id=s.elevenlabs_agent_id, conversation_token=token, mode="webrtc")
    return out


class BardChatTurn(BaseModel):
    who: str  # "you" or "bard"
    text: str


class BardChatRequest(BaseModel):
    fan_id: Optional[str] = None
    history: list[BardChatTurn] = []


class _BardReply(BaseModel):
    reply: str
    ready: bool  # knows when they found FaZe (or that they're new) and has heard about games


# Asked in order when Gemini is unavailable, so the free Bard never stalls.
_BARD_QUESTIONS = ["Who was your guy? Your favorite FaZe member, if you had one?", "And what games do you play these days?"]


@router.post("/bard/chat", tags=["hub"],
             description="The free Bard (no ElevenLabs): the browser sends the conversation so far and gets the Bard's next line. "
                         "When he knows enough, the fan is classified and done=true comes back with their fan_id.")
async def bard_chat(req: BardChatRequest):
    from app.services.bard_agent import FIRST_MESSAGE, SYSTEM_PROMPT
    from app.services.llm import generate_json
    said = [t.text.strip() for t in req.history if t.who == "you" and t.text.strip()][-6:]
    if not said:
        return {"reply": FIRST_MESSAGE, "done": False, "fan_id": req.fan_id}
    convo = "\n".join(f"{'Fan' if t.who == 'you' else 'Bard'}: {t.text}" for t in req.history[-12:])
    persona = SYSTEM_PROMPT.split("As soon as you know")[0]  # the voice and the three questions, without the tool steps
    out = await generate_json(
        f"Conversation so far:\n{convo}\n\nWrite the Bard's next line (one or two short spoken sentences, at most one question). "
        "Set ready=true once you know when they found FaZe (or that they are new) and have heard what games they play.",
        _BardReply, system=persona, timeout=8.0)
    ready = (out.ready if out else False) or len(said) >= 3  # three answers is enough, whatever the model thinks
    if not ready:
        return {"reply": out.reply if out else _BARD_QUESTIONS[min(len(said), len(_BARD_QUESTIONS)) - 1], "done": False, "fan_id": req.fan_id}
    res = await onboard_classify(ClassifyRequest(fan_id=req.fan_id, transcript=" ".join(said)))
    await store().log_event(res.fan_id, "bard_onboard", "web", {"path": res.path, "era": res.entry_era, "voice": "free"})
    when = "now" if res.entry_era == "today" else "in " + ERA_LABELS[res.entry_era].split(" · ")[0]  # spoken: "in 2013"
    line = res.bard_line.replace(" · ", " ")  # "2013 · Rug Era" reads aloud as "2013 Rug Era"
    return {"reply": f"{line} Look upon your Odyssey Map: your road begins {when}. Farewell for now, traveler.",
            "done": True, "fan_id": res.fan_id, "path": res.path, "entry_era": res.entry_era}


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


@router.post("/omen/broadcast", tags=["omen"], dependencies=[Depends(require_service_key)],
             description="Text today's omen over iMessage to everyone who opted in (texted OMEN). Run daily from cron.")
async def omen_broadcast():
    return {"omen_id": omen.today_omen()[0].omen_id, "subscribers": len(chert.subscribers()), **await chert.broadcast_omen()}


# ------------------------------------------------------------- recap video (P1)
@router.post("/recap/{fan_id}", tags=["recap"], description="Renders (or returns cached) a vertical 15s 'My FaZe Odyssey' mp4.")
async def recap_video(fan_id: str):
    from app.services import recap
    st = store()
    fan = await st.get_fan(fan_id)
    if not fan:
        raise HTTPException(404, "unknown fan")
    try:
        out = await recap.render(fan, await st.list_fan_relics(fan_id))
    except Exception as e:
        log.exception("recap failed")
        raise HTTPException(503, f"recap render failed: {e}")
    await st.log_event(fan_id, "recap", "web", {"key": out["key"]})
    return out


# ------------------------------------------------------------- twitch live trials (P1)
@router.post("/twitch/eventsub", tags=["twitch"], include_in_schema=True)
async def twitch_eventsub(request: Request):
    from fastapi.responses import PlainTextResponse
    from app.services import twitch
    from app.config import get_settings
    if not get_settings().twitch_eventsub_secret:
        raise HTTPException(503, "TWITCH_EVENTSUB_SECRET not set")
    body = await request.body()
    h = {k.lower(): v for k, v in request.headers.items()}
    if not twitch.verify(h, body):
        raise HTTPException(403, "bad signature")
    import json as _json
    msg = _json.loads(body)
    kind = h.get("twitch-eventsub-message-type")
    if kind == "webhook_callback_verification":
        return PlainTextResponse(msg["challenge"])
    if kind == "revocation":
        log.warning("twitch subscription revoked: %s", msg.get("subscription", {}).get("type"))
        return PlainTextResponse("", status_code=204)
    if twitch.seen(h.get("twitch-eventsub-message-id", "")):
        return PlainTextResponse("", status_code=204)
    res = twitch.handle(msg.get("subscription", {}).get("type", ""), msg.get("event", {}))
    log.info("twitch event -> %s", res)
    return PlainTextResponse("", status_code=204)


@router.get("/twitch/live", tags=["twitch"])
async def twitch_live():
    from app.services import twitch
    return twitch.live.snapshot()


@router.post("/twitch/live/queue", tags=["twitch"], dependencies=[Depends(require_service_key)],
             description="Manually queue a challenger (demo without a live stream).")
async def twitch_queue(login: str, display: Optional[str] = None):
    from app.services import twitch
    return {"queued": twitch.live.enqueue(login.lower(), display or login, "manual"), **twitch.live.snapshot()}


@router.post("/twitch/live/next", tags=["twitch"], dependencies=[Depends(require_service_key)])
async def twitch_next():
    from app.services import twitch
    return {"current": twitch.live.next(), **twitch.live.snapshot()}


@router.post("/twitch/live/judge", tags=["twitch"], dependencies=[Depends(require_service_key)],
             description="Judge the current challenger's trickshot from a frame (multipart image or JSON image_b64).")
async def twitch_judge(request: Request):
    from app.services import twitch
    data, mime, _ = await _read_frame(request)
    ch = twitch.live.current
    if not ch:
        raise HTTPException(409, "no current challenger; call /twitch/live/next")
    fan = await store().upsert_fan(f"twitch_{ch['login']}", handle=ch["display"])
    v = await oracle.judge(data, mime, "bow_trial", fan_id=fan["id"], context=f"Live on Twitch, challenger {ch['display']}",
                           source="twitch")
    twitch.live.recent.appendleft({"login": ch["login"], "display": ch["display"], "score": v.score, "spoken": v.spoken,
                                   "rank": v.rank, "relic": v.relic.name if v.relic else None})
    twitch.live.current = None
    return v


@router.get("/twitch/overlay", include_in_schema=False)
async def twitch_overlay():
    from fastapi.responses import FileResponse
    from app.config import BASE_DIR
    return FileResponse(BASE_DIR / "static" / "twitch.html")


# ------------------------------------------------------------- tiers + rewards
@router.get("/rewards/{fan_id}", tags=["rewards"],
            description="Tier ladder: relic-count tiers (Traveler 1, Sailor 5, Hero 10, Legend 20) + the Pass-only meet & greet.")
async def rewards_status(fan_id: str):
    from app.services import rewards
    s = await rewards.status(fan_id)
    if s is None:
        raise HTTPException(404, "unknown fan")
    return s


@router.post("/rewards/{fan_id}/claim", tags=["rewards"], description="Body: {reward_id, member?}. member is required for meet_greet.")
async def rewards_claim(fan_id: str, payload: dict, authorization: Optional[str] = Header(default=None)):
    from app.services import rewards
    check_fan(fan_id, authorization)
    try:
        return await rewards.claim(fan_id, payload.get("reward_id", ""), payload.get("member"))
    except LookupError:
        raise HTTPException(404, "unknown fan")
    except KeyError:
        raise HTTPException(404, "unknown reward")
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


# ------------------------------------------------------------- new-fan intro montage (home page)
@router.get("/intro/narration", tags=["hub"],
            description="'FaZe in 40 seconds' narration in the Bard's voice: one line + audio_url per montage slide "
                        "(audio_url null when ElevenLabs isn't available).")
async def intro_narration():
    from app.services import intro
    return await intro.narration()


# ------------------------------------------------------------- era videos (map -> YouTube -> Siren)
@router.get("/eras/{era}/videos", tags=["hub"],
            description="FaZe videos for one era of the Odyssey Map. Lore entries with a video_id link straight to the "
                        "moment (+ thumbnail); without one, a YouTube search built from the lore's find_video hint. "
                        "Opening a FaZe video is where the Siren extension takes over. Pass fan_id to mark collected relics.")
async def era_videos(era: str, fan_id: Optional[str] = None, limit: int = Query(6, ge=1, le=20)):
    from app.services.bard import youtube_url
    if era not in ERAS:
        raise HTTPException(404, f"era must be one of {ERAS}")
    have = {r["id"] for r in await store().list_fan_relics(fan_id)} if fan_id else set()
    items = []
    for e in lore().for_era(era):
        if e.get("sensitive"):
            continue
        vid = e.get("video_id")
        start = int(e.get("start_s") or 0)
        relic = e.get("relic") or {}
        items.append({
            "lore_id": e["id"], "title": e["title"], "year": e.get("year"), "summary": e.get("summary"),
            "video_id": vid, "start_s": start,
            "url": youtube_url(e),  # the moment, or a search inside the FaZe Clan channel
            "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else None,
            "kind": "moment" if vid else "search",
            "relic": {"id": relic.get("id"), "name": relic.get("name"), "rarity": relic.get("rarity"),
                      "collected": relic.get("id") in have} if relic else None,
        })
    # most-watched uploads from that era (filled by scripts.ingest_youtube --write)
    known = {i["video_id"] for i in items if i["video_id"]}
    for v in sorted([v for v in lore().video_index if v.get("era") == era and v.get("video_id") not in known],
                    key=lambda v: -(v.get("views") or 0))[:3]:
        items.append({"lore_id": None, "title": v.get("title"), "year": (v.get("published_at") or "")[:4] or None,
                      "summary": f"{v.get('channel', 'FaZe')} · {v.get('views', 0):,} views", "video_id": v["video_id"],
                      "start_s": 0, "url": f"https://www.youtube.com/watch?v={v['video_id']}",
                      "thumbnail": f"https://i.ytimg.com/vi/{v['video_id']}/hqdefault.jpg", "kind": "upload", "relic": None})
    return {"era": era, "label": ERA_LABELS[era], "videos": items[:limit]}


# ------------------------------------------------------------- Athena's quest (the guide)
@router.get("/quest/{fan_id}", tags=["quest"], description="Athena's 7-step journey for this fan: which steps are done and what's next.")
async def quest_progress(fan_id: str):
    from app.services import quest
    q = await quest.progress(fan_id)
    if q is None:
        # The browser remembers its fan across backend restarts (the memory store forgets): start them fresh
        # instead of 404ing, which used to make Athena vanish.
        await store().upsert_fan(fan_id)
        q = await quest.progress(fan_id)
    return q


@router.post("/quest/{fan_id}/mark", tags=["quest"], description="Hub-side steps: {step: 'era' | 'song' | 'oracle' | 'bow' | 'tier'} (opening a video, playing the song, visiting the Oracle / Tiers).")
async def quest_mark(fan_id: str, payload: dict):
    from app.services import quest
    if not await quest.mark(fan_id, payload.get("step", "")):
        raise HTTPException(422, "step must be one of bard, era, siren, oracle, song, bow, tier")
    return await quest.progress(fan_id)

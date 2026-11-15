"""Part B: Chert iMessage (the retention channel) + FaceTime Oracle follow-ups.

Contracts from docs.trychert.com:
- Send:    POST {CHERT_BASE_URL}/send  Authorization: Bearer <key>  {"phone": "+1...", "body": "..."}
- Inbound: webhook subscription for `message.received`; signed with
           X-Webhook-Signature: t=<ts>,v1=<hex>   (legacy x-chert-signature: v1,<ts>,<hex>)
           hex = HMAC-SHA256(subscription_secret, "<ts>.<raw_body>")
- FaceTime is a LiveKit room bridged by `chert dev`; our agent lives in oracle_agent/ and calls
  POST /chert/facetime/start + /chert/facetime/verdict on this API.

No CHERT_API_KEY = dry run: messages land in `outbox` (and the log) instead of a phone.
"""
import hashlib
import hmac
import json
import logging
import re
import time
from collections import deque
from typing import Optional

import httpx

from app.config import get_settings
from app.services.store import hash_phone, store

log = logging.getLogger("ithaca.chert")

outbox: deque = deque(maxlen=50)        # last sends, phone masked (demo/debug)
_seen_msgs: deque = deque(maxlen=500)   # webhook retries carry the same message id
_seen_set: set[str] = set()
_pending_omen: dict[str, str] = {}      # phone_hash -> omen_id we sent them and they haven't answered
_greeted: set[str] = set()              # phone hashes we've sent the welcome menu to


# ------------------------------------------------------------------ helpers
def normalize_phone(p: Optional[str]) -> Optional[str]:
    if not p:
        return None
    p = p.strip()
    if "@" in p:  # iMessage handles can be emails; pass through
        return p
    digits = re.sub(r"\D", "", p)
    if not digits:
        return None
    if len(digits) == 10:  # assume US
        digits = "1" + digits
    return "+" + digits


def mask(p: Optional[str]) -> str:
    if not p:
        return "?"
    return p[:3] + "…" + p[-2:] if len(p) > 6 else "…"


def hub_link(fan_id: Optional[str]) -> str:
    base = get_settings().hub_base_url.rstrip("/")
    return f"{base}/odyssey/{fan_id}" if fan_id else base


def facetime_hint() -> str:
    line = get_settings().chert_line
    return f"FaceTime the Oracle at {line}" if line else "FaceTime the Oracle"


# ------------------------------------------------------------------ send
async def send_imessage(phone: Optional[str], body: str) -> dict:
    """Send one iMessage through Chert. Never raises: returns a status dict."""
    s = get_settings()
    phone = normalize_phone(phone)
    if not phone or not body:
        return {"status": "skipped", "reason": "no phone or body"}
    rec = {"to": mask(phone), "body": body, "ts": time.time()}
    if not s.has_chert:
        log.info("[chert dry-run] -> %s: %s", mask(phone), body.replace("\n", " | "))
        outbox.appendleft({**rec, "status": "dry_run"})
        return {"status": "dry_run"}
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{s.chert_base_url.rstrip('/')}/send",
                             headers={"Authorization": f"Bearer {s.chert_api_key}"},
                             json={"phone": phone, "body": body})
        if r.status_code >= 400:
            log.warning("chert send failed %s: %s", r.status_code, r.text[:300])
            outbox.appendleft({**rec, "status": f"error_{r.status_code}"})
            return {"status": "error", "code": r.status_code, "detail": r.text[:300]}
        j = r.json() if r.content else {}
        outbox.appendleft({**rec, "status": j.get("status", "sent"), "message_id": j.get("message_id")})
        return {"status": j.get("status", "sent"), "message_id": j.get("message_id")}
    except Exception as e:
        log.warning("chert send error: %r", e)
        outbox.appendleft({**rec, "status": "error"})
        return {"status": "error", "detail": repr(e)}


# ------------------------------------------------------------------ webhook signature
def verify_signature(headers: dict, raw: bytes, secret: str, tolerance_s: int = 300) -> bool:
    """headers must be lower-cased."""
    ts = v1 = None
    sig = headers.get("x-webhook-signature")
    if sig:
        parts = dict(p.strip().split("=", 1) for p in sig.split(",") if "=" in p)
        ts, v1 = parts.get("t"), parts.get("v1")
    elif headers.get("x-chert-signature"):
        bits = headers["x-chert-signature"].split(",")
        if len(bits) == 3 and bits[0].strip() == "v1":
            ts, v1 = bits[1].strip(), bits[2].strip()
    if not ts or not v1:
        return False
    try:
        t = int(ts)
    except ValueError:
        return False
    t_s = t / 1000 if t > 10**12 else t  # tolerate ms timestamps
    if abs(time.time() - t_s) > tolerance_s:
        return False
    want = hmac.new(secret.encode(), ts.encode() + b"." + raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(want, v1)


# ------------------------------------------------------------------ Daily Omen opt-in list
# Phones are otherwise stored only hashed. Fans who text OMEN opt in to a daily text, so we must keep
# their number to text them; STOP removes it. File is gitignored.
def _load_optin() -> list[str]:
    p = get_settings().chert_optin_path
    try:
        return json.loads(p.read_text()) if p.exists() else []
    except Exception:
        return []


def _save_optin(phones: list[str]) -> None:
    p = get_settings().chert_optin_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(sorted(set(phones))))


def opt_in(phone: str) -> None:
    _save_optin(_load_optin() + [phone])


def opt_out(phone: str) -> None:
    _save_optin([p for p in _load_optin() if p != phone])


def subscribers() -> list[str]:
    return _load_optin()


async def send_omen(phone: str) -> dict:
    from app.services import omen
    o = omen.today_omen()[0]
    _pending_omen[hash_phone(phone)] = o.omen_id
    return await send_imessage(phone, o.imessage_text)


async def broadcast_omen() -> dict:
    res = {"sent": 0, "dry_run": 0, "failed": 0}
    for phone in subscribers():
        r = await send_omen(phone)
        key = {"dry_run": "dry_run", "error": "failed", "skipped": "failed"}.get(r["status"], "sent")
        res[key] += 1
    return res


# ------------------------------------------------------------------ inbound
def parse_inbound(payload: dict) -> Optional[dict]:
    """-> {msg_id, phone, text, has_media} for a 1:1 inbound message, else None."""
    ev = payload.get("event_type") or payload.get("type")
    data = payload.get("data") or {}
    msg = data.get("message") or {}
    if ev == "message.received" or msg:
        if (msg.get("direction") or "inbound") != "inbound" or (data.get("chat") or {}).get("is_group"):
            return None
        sender = msg.get("sender_handle") or {}
        if sender.get("is_me"):
            return None
        parts = msg.get("parts") or []
        text = " ".join(str(p.get("value") or "") for p in parts if p.get("type") == "text").strip()
        has_media = any(p.get("type") == "media" for p in parts)
        return {"msg_id": msg.get("id") or payload.get("event_id"), "phone": normalize_phone(sender.get("handle")),
                "text": text, "has_media": has_media}
    if ev == "lead_reply":  # legacy event: shape not documented, read defensively
        phone = payload.get("phone") or (payload.get("lead") or {}).get("phone") or data.get("phone")
        text = payload.get("body") or payload.get("text") or data.get("body") or ""
        return {"msg_id": payload.get("event_id") or payload.get("message_id"), "phone": normalize_phone(phone),
                "text": str(text).strip(), "has_media": False}
    return None


MENU = ("Text OMEN for a daily FaZe lore quest (Drachmae!), MAP for your Odyssey, TRIAL for this week's Bow Trial, "
        "or ask me anything about FaZe history. STOP to leave the Omen list.")


async def route(fan: dict, phone: str, text: str, has_media: bool) -> str:
    """Decide the reply to one inbound text."""
    from app.services import bard, omen
    from app.services.oracle import BOW_PASS

    st = store()
    t = text.strip()
    cmd = re.sub(r"[^a-z]", "", t.lower())
    ph = hash_phone(phone)
    first = ph not in _greeted
    _greeted.add(ph)

    if cmd in {"stop", "unsubscribe", "cancel", "end", "quit"}:
        opt_out(phone)
        _pending_omen.pop(ph, None)
        return "You've left the Omen list. The road home stays open: text OMEN to return."
    if cmd in {"omen", "start", "subscribe", "yes", "daily"}:
        opt_in(phone)
        o = omen.today_omen()[0]
        _pending_omen[ph] = o.omen_id
        return o.imessage_text + "\n(You'll get one omen a day. Text STOP anytime.)"
    if cmd in {"map", "odyssey", "home", "link", "relics", "drachmae", "points"}:
        f = await st.get_fan(fan["id"]) or fan
        n = len(await st.list_fan_relics(fan["id"]))
        return f"🏛️ Your Odyssey: {n} relic{'s' if n != 1 else ''}, {f.get('drachmae', 0)} Drachmae.\n{hub_link(fan['id'])}"
    if cmd in {"trial", "bow", "bowtrial", "leaderboard"}:
        tr = await st.current_trial()
        sp = f" (presented by {tr['sponsor']})" if tr.get("sponsor") else ""
        return (f"🏹 This week's Bow Trial{sp}: {tr['prompt']} Score {BOW_PASS}+ to earn the bow relic. "
                f"{facetime_hint()} and show it your shot.")
    if has_media and not t:
        return f"The Oracle sees best face to face. {facetime_hint()} and hold your relic up to the camera."
    if cmd in {"hi", "hello", "hey", "yo", "help", "menu", "", "sup"} or (first and len(t) < 4):
        return "🏛️ Welcome to Ithaca, traveler. I'm the Bard. " + MENU

    # an open omen? treat the text as the answer
    if _pending_omen.get(ph) == omen.today_omen()[0].omen_id:
        _pending_omen.pop(ph, None)
        res = await omen.answer(fan["id"], t)
        return res.reply

    # otherwise: Ask the Bard (grounded in lore), text only
    ans = await bard.ask(t, voice=False)
    tail = f"\n\n{MENU}" if first else ""
    return f"🎶 {ans.answer}{tail}"


async def handle_inbound(payload: dict) -> dict:
    m = parse_inbound(payload)
    if not m or not m["phone"]:
        return {"ok": True, "ignored": True}
    if m["msg_id"]:
        if m["msg_id"] in _seen_set:
            return {"ok": True, "duplicate": True}
        if len(_seen_msgs) == _seen_msgs.maxlen:
            _seen_set.discard(_seen_msgs[-1])
        _seen_msgs.appendleft(m["msg_id"])
        _seen_set.add(m["msg_id"])
    st = store()
    fan = await st.upsert_fan(None, phone=m["phone"])
    await st.log_event(fan["id"], "imessage_in", "imessage", {"media": m["has_media"]})
    reply = await route(fan, m["phone"], m["text"], m["has_media"])
    sent = await send_imessage(m["phone"], reply)
    return {"ok": True, "fan_id": fan["id"], "reply": reply, "send": sent["status"]}

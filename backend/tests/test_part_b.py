"""Part B: Bard agent tools + session, Chert iMessage webhook, FaceTime Oracle endpoints. No keys needed."""
import base64
import hashlib
import hmac
import json
import os
import time

os.environ.update({"GEMINI_API_KEY": "", "ELEVENLABS_API_KEY": "", "MONGODB_URI": "", "TIGER_DSN": "", "ITHACA_API_KEY": "",
                   "CHERT_API_KEY": "", "CHERT_WEBHOOK_SECRET": "", "ELEVENLABS_AGENT_ID": ""})

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services import chert

JPG = base64.b64decode("/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q==")
PHONE = "+14155550123"


@pytest.fixture(scope="module")
def c(tmp_path_factory):
    get_settings().chert_optin_path = tmp_path_factory.mktemp("chert") / "optin.json"
    with TestClient(app) as client:
        yield client


def inbound(text: str, msg_id: str, phone: str = PHONE, media: bool = False) -> dict:
    parts = [{"type": "text", "value": text}] if text else []
    if media:
        parts.append({"type": "media", "attachment_id": "in_1", "mime_type": "image/jpeg"})
    return {"event_id": f"chert:msg:{msg_id}", "event_type": "message.received", "data": {
        "chat": {"id": "c1", "is_group": False, "handles": []},
        "message": {"id": msg_id, "direction": "inbound", "parts": parts,
                    "sender_handle": {"handle": phone, "service": "imessage", "is_me": False}}}}


def last_to(phone: str = PHONE) -> str:
    m = next(m for m in chert.outbox if m["to"] == chert.mask(phone))
    return m["body"]


# ------------------------------------------------------------- Bard agent
def test_agent_session_unconfigured(c):
    j = c.post("/bard/agent/session", json={"handle": "Ody"}).json()
    assert j["mode"] == "unconfigured" and j["fan_id"] and j["dynamic_variables"]["fan_id"] == j["fan_id"]
    assert j["dynamic_variables"]["handle"] == "Ody" and "." in j["fan_token"]


def test_tool_classify_uses_session_fan_and_hides_token(c):
    fan_id = c.post("/bard/agent/session", json={}).json()["fan_id"]
    j = c.post("/tools/classify_fan", json={"fan_id": fan_id, "first_found_year": 2014, "games": ["Warzone"]}).json()
    assert j["fan_id"] == fan_id and j["path"] == "odysseus" and j["entry_era"] == "2013_rug_era"
    assert "fan_token" not in j and j["era_label"] and j["bard_line"]
    assert c.get(f"/odyssey/{fan_id}").json()["entry_era"] == "2013_rug_era"


def test_agent_config_shape():
    from app.services.bard_agent import agent_config, client_tools, webhook_tools
    tools = webhook_tools("https://api.example.com", "k") + client_tools()
    cfg = agent_config(inline_tools=tools)
    names = [t["name"] for t in cfg["conversation_config"]["agent"]["prompt"]["tools"]]
    assert names == ["classify_fan", "get_lore", "show_odyssey_map"]
    assert tools[0]["api_schema"]["url"] == "https://api.example.com/tools/classify_fan"
    assert tools[0]["api_schema"]["request_headers"] == {"X-Ithaca-Key": "k"}
    assert tools[0]["api_schema"]["request_body_schema"]["properties"]["fan_id"]["dynamic_variable"] == "fan_id"


def test_bard_page(c):
    assert "Speak with the Bard" in c.get("/bard").text


# ------------------------------------------------------------- Chert iMessage
def test_signature_verification():
    secret, raw = "whsec", b'{"a":1}'
    ts = str(int(time.time()))
    good = hmac.new(secret.encode(), ts.encode() + b"." + raw, hashlib.sha256).hexdigest()
    assert chert.verify_signature({"x-webhook-signature": f"t={ts},v1={good}"}, raw, secret)
    assert chert.verify_signature({"x-chert-signature": f"v1,{ts},{good}"}, raw, secret)
    assert not chert.verify_signature({"x-webhook-signature": f"t={ts},v1={'0' * 64}"}, raw, secret)
    old = str(int(time.time()) - 1000)
    sig_old = hmac.new(secret.encode(), old.encode() + b"." + raw, hashlib.sha256).hexdigest()
    assert not chert.verify_signature({"x-webhook-signature": f"t={old},v1={sig_old}"}, raw, secret)
    assert not chert.verify_signature({}, raw, secret)


def test_webhook_rejects_bad_signature(c, monkeypatch):
    monkeypatch.setattr(get_settings(), "chert_webhook_secret", "whsec")
    body = json.dumps(inbound("hi", "sig1")).encode()
    assert c.post("/chert/webhook", content=body, headers={"X-Webhook-Signature": "t=1,v1=00"}).status_code == 401
    ts = str(int(time.time()))
    sig = hmac.new(b"whsec", ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    r = c.post("/chert/webhook", content=body, headers={"X-Webhook-Signature": f"t={ts},v1={sig}"})
    assert r.status_code == 200 and r.json()["queued"]


def test_imessage_menu_omen_flow(c):
    c.post("/chert/webhook", json=inbound("hey", "m1"))
    assert "Welcome to Ithaca" in last_to()
    # duplicate delivery is ignored
    n = len(chert.outbox)
    c.post("/chert/webhook", json=inbound("hey", "m1"))
    assert len(chert.outbox) == n
    c.post("/chert/webhook", json=inbound("OMEN", "m2"))
    assert "Today's Omen" in last_to() and PHONE in chert.subscribers()
    c.post("/chert/webhook", json=inbound("no idea at all", "m3"))
    assert "Not quite" in last_to() or "omen is true" in last_to()
    c.post("/chert/webhook", json=inbound("MAP", "m4"))
    assert "/odyssey/" in last_to() and "Drachmae" in last_to()
    c.post("/chert/webhook", json=inbound("trial", "m5"))
    assert "Bow Trial" in last_to()
    c.post("/chert/webhook", json=inbound("who is Snoop to FaZe?", "m6"))
    assert last_to().startswith("🎶")
    c.post("/chert/webhook", json=inbound("", "m7", media=True))
    assert "FaceTime" in last_to()
    c.post("/chert/webhook", json=inbound("STOP", "m8"))
    assert PHONE not in chert.subscribers()


def test_ignores_outbound_and_group(c):
    p = inbound("hi", "g1")
    p["data"]["chat"]["is_group"] = True
    assert c.post("/chert/webhook", json=p).json()["ignored"]
    p = inbound("hi", "o1")
    p["data"]["message"]["direction"] = "outbound"
    assert c.post("/chert/webhook", json=p).json()["ignored"]


def test_omen_broadcast(c):
    chert.opt_in("+14155550999")
    j = c.post("/omen/broadcast").json()
    assert j["subscribers"] >= 1 and j["dry_run"] >= 1
    assert "Today's Omen" in last_to("+14155550999")


def test_send_and_outbox(c):
    assert c.post("/chert/send", json={"phone": "(415) 555-0177", "body": "yo"}).json()["status"] == "dry_run"
    out = c.get("/chert/outbox").json()
    assert out["live"] is False and out["messages"][0]["body"] == "yo" and "0177" not in out["messages"][0]["to"]


# ------------------------------------------------------------- FaceTime Oracle
def test_facetime_flow(c):
    phone = "+14155550456"
    s = c.post("/chert/facetime/start", json={"call_id": "room1", "phone": phone}).json()
    assert s["fan_id"] and s["greeting"] and s["known"] is False
    r = c.post("/chert/facetime/verdict", files={"image": ("f.jpg", JPG, "image/jpeg")},
               data={"mode": "argos", "call_id": "room1", "phone": phone}).json()
    assert r["say"] and r["fan_id"] == s["fan_id"] and r["imessage"] == "queued"
    assert "The Oracle has spoken" in last_to(phone)
    # second argos look in the same call doesn't re-text
    r2 = c.post("/chert/facetime/verdict", files={"image": ("f.jpg", JPG, "image/jpeg")},
                data={"mode": "argos", "call_id": "room1", "phone": phone}).json()
    assert r2["imessage"] == "not_sent"
    b = c.post("/chert/facetime/verdict", json={"image_b64": base64.b64encode(JPG).decode(), "mode": "bow_trial",
                                                 "call_id": "room1", "phone": phone}).json()
    assert b["verdict"]["score"] is not None and b["verdict"]["rank"] is None  # fallback: not ranked
    # caller is now known on the next call
    assert c.post("/chert/facetime/start", json={"call_id": "room2", "phone": phone}).json()["known"]


def test_facetime_anonymous_caller(c):
    r = c.post("/chert/facetime/verdict", files={"image": ("f.jpg", JPG, "image/jpeg")},
               data={"mode": "argos", "call_id": "anon1"}).json()
    assert r["fan_id"] == "ft_anon1" and r["imessage"] == "not_sent"


def test_facetime_needs_service_key(c, monkeypatch):
    monkeypatch.setattr(get_settings(), "ithaca_api_key", "k")
    assert c.post("/chert/facetime/start", json={"call_id": "x"}).status_code == 401
    assert c.post("/chert/facetime/start", json={"call_id": "x"}, headers={"X-Ithaca-Key": "k"}).status_code == 200
    # unsigned Chert webhook falls back to the service key
    assert c.post("/chert/webhook", json=inbound("hi", "k1")).status_code == 401
    assert c.post("/chert/webhook?key=k", json=inbound("hi", "k2")).status_code == 200

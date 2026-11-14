"""Smoke tests: every endpoint in no-key mode.  Run from backend/:  pytest -q"""
import base64
import os

os.environ.update({"GEMINI_API_KEY": "", "ELEVENLABS_API_KEY": "", "MONGODB_URI": "", "TIGER_DSN": "", "ITHACA_API_KEY": ""})

import pytest
from fastapi.testclient import TestClient

from app.main import app

# 1x1 jpeg
JPG = base64.b64decode("/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q==")


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module")
def fan(c):
    r = c.post("/onboard/classify", json={"handle": "t", "first_found_year": 2011, "games": ["Warzone"]})
    assert r.status_code == 200
    j = r.json()
    assert j["path"] == "odysseus" and j["entry_era"] == "2010_trickshots" and "." in j["fan_token"]
    return j["fan_id"]


def test_health(c):
    assert c.get("/health").json()["ok"]


def test_classify_new_fan(c):
    j = c.post("/tools/classify_fan", json={"transcript": "found FaZe this year through Kaysan"}).json()
    assert j["path"] == "telemachus"


def test_odyssey_and_demo_fan(c, fan):
    j = c.get(f"/odyssey/{fan}").json()
    assert len(j["map"]) == 5 and j["map"][0]["is_entry"]
    d = c.get("/odyssey/demo_odysseus").json()
    assert d["path"] == "odysseus" and len(d["relics"]) >= 2
    assert c.get("/odyssey/nope").status_code == 404


def test_episode(c, fan):
    j = c.post("/bard/episode", json={"fan_id": fan, "voice": False}).json()
    assert j["script"] and j["cues"] and j["era"] == "2010_trickshots"


def test_ask(c):
    j = c.post("/bard/ask", json={"question": "who is Snoop to FaZe?", "voice": False}).json()
    assert "Snoop" in j["answer"]


def test_oracle_argos_multipart(c, fan):
    r = c.post("/oracle/frame", files={"image": ("f.jpg", JPG, "image/jpeg")}, data={"mode": "argos", "fan_id": fan})
    j = r.json()
    assert r.status_code == 200 and j["spoken"] and j["imessage_text"] and j["share_url"].endswith(fan)


def test_oracle_bow_json_and_leaderboard(c, fan):
    b64 = "data:image/jpeg;base64," + base64.b64encode(JPG).decode()
    j = c.post("/oracle/frame", json={"image_b64": b64, "mode": "bow_trial", "fan_id": fan}).json()
    assert j["score"] is not None and j["trial_id"] and j["rank"]
    lb = c.get("/trials/leaderboard").json()
    assert any(s["fan_id"] == fan for s in lb["suitors"])


def test_oracle_bad_mode(c):
    assert c.post("/oracle/frame", files={"image": ("f.jpg", JPG, "image/jpeg")}, data={"mode": "x"}).status_code == 422


def test_sponsored_trial(c, fan):
    c.post("/trials/current", params={"sponsor": "Red Bull"})
    assert c.get("/trials/current").json()["sponsor"] == "Red Bull"
    b64 = base64.b64encode(JPG).decode()
    j = c.post("/oracle/frame", json={"image_b64": b64, "mode": "bow_trial", "fan_id": fan}).json()
    assert j["sponsor"] == "Red Bull" and "Red Bull" in j["imessage_text"]


def test_siren_consistent(c, fan):
    ctx = c.get("/siren/context", params={"videoId": "vid1", "t": 5, "channel": "FaZe Clan"}).json()
    assert ctx["is_faze"] and ctx["lore"]
    col = c.post("/siren/collect", json={"fan_id": fan, "video_id": "vid1", "t": 5}).json()
    assert col["relic"]["id"] == ctx["relic_available"]["id"]
    assert not c.get("/siren/context", params={"videoId": "x", "channel": "MrBeast"}).json()["is_faze"]


def test_pass_and_warroom(c, fan):
    assert c.post("/pass/checkout", params={"fan_id": fan}).json()["ok"]
    assert c.get(f"/odyssey/{fan}").json()["has_pass"]
    m = c.get("/warroom/metrics").json()
    assert m["simulated"] and m["totals"]["fans"] > 0 and len(m["daily"]) == 14


def test_omen(c, fan):
    o = c.get("/omen/today").json()
    assert o["question"] and o["imessage_text"]
    r = c.post("/omen/answer", json={"fan_id": fan, "answer": "no idea"}).json()
    assert "reply" in r
    again = c.post("/omen/answer", json={"fan_id": fan, "answer": "x"}).json()
    assert again["already_answered"]


def test_service_key_enforced(c, monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "ithaca_api_key", "k")
    assert c.post("/tools/get_lore", json={"query": "x"}).status_code == 401
    assert c.post("/tools/get_lore", json={"query": "x"}, headers={"X-Ithaca-Key": "k"}).status_code == 200

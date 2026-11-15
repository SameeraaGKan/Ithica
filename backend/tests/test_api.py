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


def test_recap(c):
    j = c.post("/recap/demo_odysseus").json()
    assert j["video_url"].endswith(".mp4")
    assert c.post("/recap/demo_odysseus").json()["cached"]


def test_twitch_flow(c):
    import hashlib, hmac, json
    from datetime import datetime, timezone
    from app.config import get_settings
    s = get_settings()
    s.twitch_eventsub_secret = "testsecret123"
    body = json.dumps({"subscription": {"type": "channel.chat.message"},
                       "event": {"broadcaster_user_login": "me", "chatter_user_login": "viewer1",
                                 "chatter_user_name": "Viewer1", "message": {"text": "!bow let me in"}}}).encode()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.123456789Z")
    sig = "sha256=" + hmac.new(b"testsecret123", b"m1" + ts.encode() + body, hashlib.sha256).hexdigest()
    h = {"Twitch-Eventsub-Message-Id": "m1", "Twitch-Eventsub-Message-Timestamp": ts,
         "Twitch-Eventsub-Message-Signature": sig, "Twitch-Eventsub-Message-Type": "notification"}
    assert c.post("/twitch/eventsub", content=body, headers=h).status_code == 204
    assert c.post("/twitch/eventsub", content=body, headers={**h, "Twitch-Eventsub-Message-Signature": "sha256=bad"}).status_code == 403
    assert c.get("/twitch/live").json()["queue"][0]["login"] == "viewer1"
    assert c.post("/twitch/live/next").json()["current"]["login"] == "viewer1"
    v = c.post("/twitch/live/judge", files={"image": ("f.jpg", JPG, "image/jpeg")}).json()
    assert v["score"] is not None and c.get("/twitch/live").json()["recent"][0]["login"] == "viewer1"
    s.twitch_eventsub_secret = ""


def test_captions_parse():
    from app.services.transcripts import chunk, parse_captions
    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:04.000\nyo we hit 1 million\n\n00:00:04.000 --> 00:00:40.000\n<c>thank you</c> guys\n"
    segs = parse_captions(vtt)
    assert [x.text for x in segs] == ["yo we hit 1 million", "thank you guys"]
    assert chunk(segs)[0]["start_s"] == 1


def test_test_page(c):
    r = c.get("/test")
    assert r.status_code == 200 and "API test page" in r.text


def test_hub_contract(c):
    """Fields the Next.js Hub (frontend/) relies on."""
    o = c.get("/odyssey/demo_odysseus").json()
    assert "locked_relics" in o and "games" in o and o["locked_relics"]
    before = len(o["relics"])
    col = c.post("/siren/collect", json={"fan_id": "demo_odysseus"}).json()  # Hub demo button: no video
    assert col["relic"] and not col["already_had"]
    assert len(c.get("/odyssey/demo_odysseus").json()["relics"]) == before + 1
    rid = o["locked_relics"][-1]["id"]
    assert c.post("/siren/collect", json={"fan_id": "demo_odysseus", "relic_id": rid}).json()["relic"]["id"] == rid
    m = c.get("/warroom/metrics").json()
    assert m["funnel"] and "generated_at" in m and {"pass_cents", "drops_cents", "sponsored_cents"} <= set(m["daily"][0])
    lb = c.get("/trials/leaderboard").json()["suitors"]
    assert "path" in lb[0] and "drachmae" in lb[0]


def test_rewards_tiers_and_pass(c):
    f = c.post("/onboard/classify", json={"handle": "tier", "first_found_year": 2014}).json()["fan_id"]
    s = c.get(f"/rewards/{f}").json()
    assert s["relics"] == 0 and s["tier"] is None and s["next_tier"]["id"] == "traveler"
    assert c.post(f"/rewards/{f}/claim", json={"reward_id": "traveler"}).status_code == 403
    c.post("/siren/collect", json={"fan_id": f})  # one relic -> Traveler
    s = c.get(f"/rewards/{f}").json()
    assert s["tier"]["id"] == "traveler" and s["next_tier"]["relics_to_go"] == 4
    claim = c.post(f"/rewards/{f}/claim", json={"reward_id": "traveler"}).json()
    assert claim["code"].startswith("ITH-")
    mg = next(r for r in c.get(f"/rewards/{f}").json()["rewards"] if r["id"] == "meet_greet")
    assert mg["requires_pass"] and not mg["unlocked"]
    assert c.post(f"/rewards/{f}/claim", json={"reward_id": "meet_greet", "member": "Rug"}).status_code == 403
    c.post("/pass/checkout", params={"fan_id": f})
    assert c.post(f"/rewards/{f}/claim", json={"reward_id": "meet_greet"}).status_code == 422  # must pick a member
    ok = c.post(f"/rewards/{f}/claim", json={"reward_id": "meet_greet", "member": "Rug"}).json()
    assert "Rug" in ok["message"]


def test_era_videos(c):
    j = c.get("/eras/2010_trickshots/videos", params={"fan_id": "demo_odysseus"}).json()
    assert j["videos"] and all(v["url"].startswith("https://www.youtube.com/") for v in j["videos"])
    assert any(v["relic"] and v["relic"]["collected"] for v in j["videos"])  # demo fan holds a 2010 relic
    assert c.get("/eras/nope/videos").status_code == 404


def test_siren_member_channels(c):
    ctx = lambda ch: c.get("/siren/context", params={"videoId": "vid9", "channel": ch}).json()["is_faze"]
    assert ctx("FaZe Clan") and ctx("FaZe Rug") and ctx("Swagg") and ctx("Stable Ronaldo") and ctx("@jarvis")
    assert not ctx("SwaggerGaming") and not ctx("MrBeast") and not ctx("Rugby Highlights")


def test_athena_quest(c):
    f = c.post("/onboard/classify", json={"handle": "q", "first_found_year": 2013}).json()["fan_id"]
    q = c.get(f"/quest/{f}").json()
    assert q["total"] == 7 and q["steps"][0]["done"] and q["current"]["key"] == "era"
    q = c.post(f"/quest/{f}/mark", json={"step": "era"}).json()
    assert q["current"]["key"] == "siren"
    c.post("/siren/collect", json={"fan_id": f, "video_id": "abc", "channel": "FaZe Clan"})
    assert c.get(f"/quest/{f}").json()["current"]["key"] == "oracle"
    c.post("/oracle/frame", files={"image": ("f.jpg", JPG, "image/jpeg")}, data={"mode": "argos", "fan_id": f})
    c.post(f"/quest/{f}/mark", json={"step": "song"})
    c.post("/oracle/frame", files={"image": ("f.jpg", JPG, "image/jpeg")}, data={"mode": "bow_trial", "fan_id": f})
    assert c.get(f"/quest/{f}").json()["current"]["key"] == "tier"
    c.post(f"/rewards/{f}/claim", json={"reward_id": "traveler"})
    q = c.get(f"/quest/{f}").json()
    assert q["completed"] == 7 and q["current"] is None
    assert c.post(f"/quest/{f}/mark", json={"step": "nope"}).status_code == 422
    g = c.post("/onboard/classify", json={"handle": "skip"}).json()["fan_id"]
    c.post(f"/quest/{g}/mark", json={"step": "era"})
    assert c.post(f"/quest/{g}/mark", json={"step": "siren"}).json()["current"]["key"] == "oracle"  # ticked by hand


def test_athena_visits_count(c):
    f = c.post("/onboard/classify", json={"handle": "v", "first_found_year": 2013}).json()["fan_id"]
    for step in ("era",):
        c.post(f"/quest/{f}/mark", json={"step": step})
    c.post("/siren/collect", json={"fan_id": f, "video_id": "abc"})
    assert c.get(f"/quest/{f}").json()["current"]["key"] == "oracle"
    assert c.post(f"/quest/{f}/mark", json={"step": "oracle"}).json()["current"]["key"] == "song"  # visiting is enough
    c.post(f"/quest/{f}/mark", json={"step": "song"})
    assert c.post(f"/quest/{f}/mark", json={"step": "bow"}).json()["current"]["key"] == "tier"
    assert c.post(f"/quest/{f}/mark", json={"step": "tier"}).json()["completed"] == 7

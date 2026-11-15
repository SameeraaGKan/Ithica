"""The Oracle on FaceTime (Part B).

Chert bridges a FaceTime call into a LiveKit room (`chert dev --agent ithaca-oracle`). This worker joins the
room, watches the caller's camera (`facetime-remote-video`), sends frames to the ITHACA API, and speaks the
verdict in the Bard/Oracle ElevenLabs voice. The API sends the iMessage relic card after the call moment.

Scripted, deterministic demo flow (no speech recognition needed, so nothing to mishear on a loud floor):
  1. Greeting (personal if the caller's number is a known fan).
  2. ARGOS REMEMBERS: "hold your FaZe relic to the light" -> up to 3 looks -> era verdict + relic.
  3. THE BOW TRIAL: "play your best trickshot on a screen" -> one look -> score + leaderboard rank.
  4. Farewell: "your relic card sails to you by iMessage".
Every network step has a canned line, so the Oracle never goes silent.

Run:  python agent.py dev      (and in another terminal: chert dev --agent ithaca-oracle)
"""
import asyncio
import io
import json
import logging
import os
import re
import time
from typing import Optional

import httpx
from dotenv import load_dotenv
from PIL import Image, ImageStat

from livekit import rtc
from livekit.agents import Agent, AgentSession, AutoSubscribe, JobContext, RoomInputOptions, WorkerOptions, cli
from livekit.plugins import elevenlabs

load_dotenv(".env.local")
load_dotenv()
log = logging.getLogger("ithaca.oracle_agent")

API = os.getenv("ITHACA_API_URL", "http://localhost:8000").rstrip("/")
KEY = os.getenv("ITHACA_API_KEY", "")
AGENT_NAME = os.getenv("ORACLE_AGENT_NAME", "ithaca-oracle")
VIDEO_TRACK = "facetime-remote-video"
PHONE_RE = re.compile(r"\+?\d[\d\s().-]{8,}\d")

CANNED = {
    "argos": "The mists are thick, but I sense an old soul of FaZe. Welcome home, traveler. Ithaca kept your place.",
    "bow_trial": "A bold shot. The suitors grow nervous. I name it worthy. Return next week and string the bow again.",
}


# ------------------------------------------------------------------ caller video
class FrameGrabber:
    """Keeps only the latest caller frame (and when it arrived). Frames never leave memory except to the API."""

    def __init__(self) -> None:
        self.frame: Optional[rtc.VideoFrame] = None
        self.at = 0.0
        self.track_seen = asyncio.Event()
        self._task: Optional[asyncio.Task] = None

    def attach(self, track: rtc.Track, name: str) -> None:
        if track.kind != rtc.TrackKind.KIND_VIDEO:
            return
        # prefer Chert's named caller track; take any remote video until we see it
        if self._task and name != VIDEO_TRACK:
            return
        if self._task:
            self._task.cancel()
        log.info("watching video track %r", name)
        self.track_seen.set()
        self._task = asyncio.create_task(self._pump(track))

    async def _pump(self, track: rtc.Track) -> None:
        async for ev in rtc.VideoStream(track):
            self.frame, self.at = ev.frame, time.monotonic()

    def jpeg(self, max_age_s: float = 2.5) -> Optional[bytes]:
        """Latest frame as JPEG, or None if stale (camera muted / capture lost) or near-black."""
        if not self.frame or time.monotonic() - self.at > max_age_s:
            return None
        f = self.frame.convert(rtc.VideoBufferType.RGBA)
        img = Image.frombytes("RGBA", (f.width, f.height), bytes(f.data)).convert("RGB")
        if max(ImageStat.Stat(img).mean) < 10:  # muted cameras often send black
            return None
        img.thumbnail((768, 768))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=82)
        return buf.getvalue()


# ------------------------------------------------------------------ caller identity
def find_phone(ctx: JobContext, p: rtc.RemoteParticipant) -> Optional[str]:
    """Chert's docs don't publish where the caller's number lives in the room, so look everywhere it could be.
    Confirm at the Chert table and pin this down (log line below shows what arrived)."""
    blobs: dict[str, str] = {}
    blobs.update({f"attr.{k}": v for k, v in (p.attributes or {}).items()})
    for label, raw in (("participant.metadata", p.metadata), ("room.metadata", ctx.room.metadata),
                       ("job.metadata", getattr(ctx.job, "metadata", ""))):
        if not raw:
            continue
        try:
            j = json.loads(raw)
            if isinstance(j, dict):
                blobs.update({f"{label}.{k}": str(v) for k, v in j.items()})
                continue
        except Exception:
            pass
        blobs[label] = raw
    blobs["identity"] = p.identity
    log.info("caller info keys: %s", sorted(blobs))
    prefer = [k for k in blobs if any(w in k.lower() for w in ("phone", "caller", "from", "handle", "remote"))]
    for k in prefer + [k for k in blobs if k not in prefer]:
        m = PHONE_RE.search(blobs[k] or "")
        if m:
            return m.group(0)
    return None


# ------------------------------------------------------------------ API
class Ithaca:
    def __init__(self) -> None:
        self.http = httpx.AsyncClient(base_url=API, timeout=12, headers={"X-Ithaca-Key": KEY} if KEY else {})

    async def start(self, call_id: str, phone: Optional[str]) -> dict:
        try:
            r = await self.http.post("/chert/facetime/start", json={"call_id": call_id, "phone": phone})
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.warning("start failed: %r", e)
            return {"fan_id": None, "greeting": "Welcome, traveler. I am the Oracle of Ithaca. I see what others cannot."}

    async def verdict(self, img: bytes, mode: str, call_id: str, phone: Optional[str], fan_id: Optional[str]) -> dict:
        data = {"mode": mode, "call_id": call_id, "context": "Live on FaceTime"}
        if phone:
            data["phone"] = phone
        if fan_id:
            data["fan_id"] = fan_id
        try:
            r = await self.http.post("/chert/facetime/verdict", data=data, files={"image": ("frame.jpg", img, "image/jpeg")})
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.warning("verdict failed: %r", e)
            return {"say": CANNED[mode], "verdict": {"recognized": True, "fallback": True}}


# ------------------------------------------------------------------ the call
async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect(auto_subscribe=AutoSubscribe.SUBSCRIBE_ALL)
    caller = await ctx.wait_for_participant()
    call_id = ctx.room.name or ctx.job.id
    log.info("call %s: caller %s", call_id, caller.identity)

    grab = FrameGrabber()
    ctx.room.on("track_subscribed", lambda track, pub, part: grab.attach(track, pub.name))
    for part in ctx.room.remote_participants.values():
        for pub in part.track_publications.values():
            if pub.track:
                grab.attach(pub.track, pub.name)

    tts_kw = {"model": os.getenv("ELEVENLABS_TTS_MODEL", "eleven_flash_v2_5")}
    if os.getenv("ELEVENLABS_VOICE_ID"):
        tts_kw["voice_id"] = os.environ["ELEVENLABS_VOICE_ID"]
    if os.getenv("ELEVENLABS_API_KEY"):
        tts_kw["api_key"] = os.environ["ELEVENLABS_API_KEY"]  # else the plugin reads ELEVEN_API_KEY
    session = AgentSession(tts=elevenlabs.TTS(**tts_kw))
    await session.start(room=ctx.room, agent=Agent(instructions="You are the Oracle of Ithaca."),
                        room_input_options=RoomInputOptions(audio_enabled=False))

    async def speak(text: str) -> None:
        await session.say(text, allow_interruptions=False).wait_for_playout()

    api = Ithaca()
    phone = find_phone(ctx, caller)
    hello = await api.start(call_id, phone)
    fan_id = hello.get("fan_id")
    await speak(hello["greeting"])

    try:
        await asyncio.wait_for(grab.track_seen.wait(), timeout=8)
    except asyncio.TimeoutError:
        await speak("I hear you, traveler, but I cannot see you. Call me again on FaceTime video, "
                    "and bring something from your FaZe past.")
        await asyncio.sleep(2)
        ctx.shutdown(reason="no video")
        return

    async def look(mode: str, attempts: int, wait_s: float) -> dict:
        """Wait, grab a fresh frame, judge it. Retries only while the Oracle doesn't recognize anything."""
        res: dict = {}
        for i in range(attempts):
            await asyncio.sleep(wait_s)
            img = grab.jpeg()
            if img is None:
                await speak("The vision is dark. Turn your camera toward the light.")
                continue
            res = await api.verdict(img, mode, call_id, phone, fan_id)
            await speak(res["say"])
            if res.get("verdict", {}).get("recognized") or i == attempts - 1:
                return res
        if not res:
            await speak(CANNED[mode])
        return res

    # 1. Argos Remembers
    await speak("Show me a relic of your past. A FaZe hoodie, a poster, your old setup. Hold it up to the light.")
    await look("argos", attempts=3, wait_s=3.5)

    # 2. The Bow Trial
    await speak("Now, the Bow Trial. Only the true king strings the bow. Play your best trickshot on a screen "
                "and hold it to the camera. I watch for five heartbeats.")
    bow = await look("bow_trial", attempts=1, wait_s=5)
    rank = (bow.get("verdict") or {}).get("rank")
    if rank:
        await speak(f"You stand at rank {rank} among the suitors this week.")

    # 3. Farewell
    await speak("Your relic card sails to you now by iMessage. Ithaca awaits your return, traveler. Farewell."
                if phone else "Ithaca awaits your return, traveler. Farewell.")
    await asyncio.sleep(3)
    await api.http.aclose()
    ctx.shutdown(reason="oracle finished")


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name=AGENT_NAME))

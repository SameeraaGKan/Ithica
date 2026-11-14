"""Live Bow Trials on Twitch (P1).
EventSub (webhook transport) -> chat command `!bow` or a channel-points redemption queues a
challenger -> streamer pulls the next challenger -> Oracle judges the frame live -> verdict shows
on the OBS overlay and lands on the weekly Suitors leaderboard."""
import hashlib
import hmac
import logging
import time
from collections import deque
from typing import Optional

from app.config import get_settings

log = logging.getLogger("ithaca.twitch")

MAX_AGE_S = 600
_seen: deque[str] = deque(maxlen=2000)
COMMANDS = {"!bow", "!trial", "!string"}
REWARD_TITLES = {"bow trial", "string the bow", "ithaca bow trial"}


class LiveTrial:
    def __init__(self) -> None:
        self.queue: list[dict] = []
        self.current: Optional[dict] = None
        self.recent: deque[dict] = deque(maxlen=10)
        self.chat_lines: deque[dict] = deque(maxlen=20)
        self.channel: Optional[str] = None
        self.online = False

    def enqueue(self, login: str, display: str, via: str) -> bool:
        if (self.current and self.current["login"] == login) or any(q["login"] == login for q in self.queue):
            return False
        if len(self.queue) >= 25:
            return False
        self.queue.append({"login": login, "display": display, "via": via, "ts": time.time()})
        return True

    def next(self) -> Optional[dict]:
        self.current = self.queue.pop(0) if self.queue else None
        return self.current

    def snapshot(self) -> dict:
        return {"channel": self.channel, "online": self.online, "current": self.current, "queue": self.queue,
                "recent": list(self.recent), "chat": list(self.chat_lines)}


live = LiveTrial()


def verify(headers: dict, body: bytes) -> bool:
    """Twitch EventSub HMAC: sha256(secret, message_id + timestamp + raw_body)."""
    secret = get_settings().twitch_eventsub_secret
    if not secret:
        return False
    mid = headers.get("twitch-eventsub-message-id", "")
    ts = headers.get("twitch-eventsub-message-timestamp", "")
    sig = headers.get("twitch-eventsub-message-signature", "")
    expected = "sha256=" + hmac.new(secret.encode(), (mid + ts).encode() + body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return False
    return _age(ts) < MAX_AGE_S


def _age(ts: str) -> float:
    """Twitch sends RFC3339 with up to 9 fractional digits, e.g. 2026-11-14T22:01:02.123456789Z."""
    from datetime import datetime, timezone
    try:
        base, _, frac = ts.rstrip("Z").partition(".")
        dt = datetime.fromisoformat(base).replace(tzinfo=timezone.utc)
        return time.time() - dt.timestamp() - float("0." + (frac or "0"))
    except Exception:
        return float("inf")


def seen(message_id: str) -> bool:
    if message_id in _seen:
        return True
    _seen.append(message_id)
    return False


def handle(sub_type: str, event: dict) -> Optional[dict]:
    """Returns a small description of what happened (for logs/tests)."""
    if sub_type == "channel.chat.message":
        login = event.get("chatter_user_login", "")
        display = event.get("chatter_user_name", login)
        text = ((event.get("message") or {}).get("text") or "").strip()
        live.channel = event.get("broadcaster_user_login") or live.channel
        word = text.split()[0].lower() if text else ""
        if word in COMMANDS:
            ok = live.enqueue(login, display, "chat")
            live.chat_lines.append({"user": display, "text": text, "queued": ok})
            return {"action": "queued" if ok else "duplicate", "login": login}
        return None
    if sub_type == "channel.channel_points_custom_reward_redemption.add":
        title = ((event.get("reward") or {}).get("title") or "").lower()
        if title in REWARD_TITLES:
            ok = live.enqueue(event.get("user_login", ""), event.get("user_name", ""), "channel_points")
            return {"action": "queued" if ok else "duplicate", "login": event.get("user_login")}
        return None
    if sub_type == "stream.online":
        live.online, live.channel = True, event.get("broadcaster_user_login")
        return {"action": "online"}
    if sub_type == "stream.offline":
        live.online = False
        return {"action": "offline"}
    return None

"""Create Twitch EventSub (webhook) subscriptions pointing at our Vultr URL.

Usage (from backend/):
  python -m scripts.twitch_subscribe --broadcaster faze --bot-user ithacabot
  python -m scripts.twitch_subscribe --list
  python -m scripts.twitch_subscribe --clear

Needs TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET, TWITCH_EVENTSUB_SECRET, and PUBLIC_BASE_URL (https, port 443).

Auth notes (Twitch rules, not ours):
- stream.online/offline: app token only, works for any channel.
- channel.chat.message over webhooks: the bot user must have authorized this client with
  user:read:chat + user:bot, and the broadcaster with channel:bot (or the bot is a mod).
  Easiest for the demo: use YOUR OWN channel as broadcaster and yourself as bot user, authorize once at
  https://id.twitch.tv/oauth2/authorize?response_type=token&client_id=<id>&redirect_uri=http://localhost&scope=user:read:chat+user:bot+channel:bot+channel:read:redemptions
- channel points redemptions: broadcaster must have authorized channel:read:redemptions."""
import argparse
import asyncio

import httpx

from app.config import get_settings

HELIX = "https://api.twitch.tv/helix"


async def app_token(c: httpx.AsyncClient) -> str:
    s = get_settings()
    r = await c.post("https://id.twitch.tv/oauth2/token", params={"client_id": s.twitch_client_id,
                                                               "client_secret": s.twitch_client_secret,
                                                               "grant_type": "client_credentials"})
    r.raise_for_status()
    return r.json()["access_token"]


async def user_id(c: httpx.AsyncClient, h: dict, login: str) -> str:
    r = await c.get(f"{HELIX}/users", params={"login": login}, headers=h)
    r.raise_for_status()
    data = r.json()["data"]
    if not data:
        raise SystemExit(f"no twitch user {login}")
    return data[0]["id"]


async def main(a) -> None:
    s = get_settings()
    assert s.twitch_client_id and s.twitch_client_secret and s.twitch_eventsub_secret, "Twitch env vars missing"
    async with httpx.AsyncClient(timeout=15) as c:
        h = {"Client-Id": s.twitch_client_id, "Authorization": f"Bearer {await app_token(c)}"}
        if a.list or a.clear:
            subs = (await c.get(f"{HELIX}/eventsub/subscriptions", headers=h)).json().get("data", [])
            for sub in subs:
                print(sub["id"], sub["type"], sub["status"], sub["transport"].get("callback"))
                if a.clear:
                    await c.delete(f"{HELIX}/eventsub/subscriptions", params={"id": sub["id"]}, headers=h)
            return
        b = await user_id(c, h, a.broadcaster)
        bot = await user_id(c, h, a.bot_user or a.broadcaster)
        transport = {"method": "webhook", "callback": f"{s.public_base_url.rstrip('/')}/twitch/eventsub",
                     "secret": s.twitch_eventsub_secret}
        wanted = [
            ("stream.online", "1", {"broadcaster_user_id": b}),
            ("stream.offline", "1", {"broadcaster_user_id": b}),
            ("channel.chat.message", "1", {"broadcaster_user_id": b, "user_id": bot}),
            ("channel.channel_points_custom_reward_redemption.add", "1", {"broadcaster_user_id": b}),
        ]
        for typ, ver, cond in wanted:
            r = await c.post(f"{HELIX}/eventsub/subscriptions", headers=h,
                             json={"type": typ, "version": ver, "condition": cond, "transport": transport})
            print(f"{typ:55} {r.status_code} {r.json().get('message', 'ok') if r.status_code >= 300 else 'ok'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--broadcaster")
    ap.add_argument("--bot-user")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--clear", action="store_true")
    a = ap.parse_args()
    if not (a.list or a.clear or a.broadcaster):
        ap.error("--broadcaster required")
    asyncio.run(main(a))

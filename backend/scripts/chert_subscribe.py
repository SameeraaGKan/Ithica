"""Subscribe our API to Chert's inbound iMessage events (Part B).

    python -m scripts.chert_subscribe                  # POST {PUBLIC_BASE_URL}/chert/webhook for message.received
    python -m scripts.chert_subscribe --list           # show existing subscriptions

Put the returned secret in CHERT_WEBHOOK_SECRET so /chert/webhook verifies X-Webhook-Signature.
No public URL yet? `GET {CHERT_BASE_URL}/events/stream` (SSE) works for local dev; see docs/part-b-voice-facetime.md.
"""
import argparse
import asyncio
import json
import sys

import httpx

from app.config import get_settings


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    s = get_settings()
    if not s.has_chert:
        sys.exit("CHERT_API_KEY is not set")
    base = s.chert_base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=15, headers={"Authorization": f"Bearer {s.chert_api_key}"}) as c:
        if args.list:
            r = await c.get(f"{base}/webhook-subscriptions")
        else:
            url = f"{s.public_base_url.rstrip('/')}/chert/webhook"
            r = await c.post(f"{base}/webhook-subscriptions", json={"url": url, "events": ["message.received"]})
    print(r.status_code)
    try:
        j = r.json()
        print(json.dumps(j, indent=2))
        secret = j.get("secret") or j.get("signing_secret") or (j.get("data") or {}).get("secret")
        if secret:
            print(f"\nAdd to backend/.env:\nCHERT_WEBHOOK_SECRET={secret}")
    except Exception:
        print(r.text[:2000])


if __name__ == "__main__":
    asyncio.run(main())

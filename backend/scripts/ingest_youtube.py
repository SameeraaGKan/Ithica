"""Ingest worker: pull FaZe channel uploads (titles, dates, views) via YouTube Data API v3
into video_index. Writes to Atlas if MONGODB_URI is set, and always into data/lore_seed.json.

Usage (from backend/):  python -m scripts.ingest_youtube --handle @FaZeClan --max 200
Repeat --handle for more channels. Needs YOUTUBE_API_KEY."""
import argparse
import asyncio
import json

import httpx

from app.config import get_settings
from app.services.classify import era_for_year

API = "https://www.googleapis.com/youtube/v3"


async def channel_uploads(c: httpx.AsyncClient, key: str, handle: str) -> tuple[str, str]:
    r = await c.get(f"{API}/channels", params={"part": "contentDetails,snippet", "forHandle": handle, "key": key})
    r.raise_for_status()
    items = r.json().get("items") or []
    if not items:
        raise SystemExit(f"channel not found: {handle}")
    ch = items[0]
    return ch["snippet"]["title"], ch["contentDetails"]["relatedPlaylists"]["uploads"]


async def playlist_video_ids(c: httpx.AsyncClient, key: str, playlist: str, limit: int) -> list[str]:
    ids, token = [], None
    while len(ids) < limit:
        r = await c.get(f"{API}/playlistItems", params={"part": "contentDetails", "playlistId": playlist, "maxResults": 50,
                                                        "pageToken": token, "key": key})
        r.raise_for_status()
        j = r.json()
        ids += [i["contentDetails"]["videoId"] for i in j.get("items", [])]
        token = j.get("nextPageToken")
        if not token:
            break
    return ids[:limit]


async def video_details(c: httpx.AsyncClient, key: str, ids: list[str], channel: str) -> list[dict]:
    out = []
    for i in range(0, len(ids), 50):
        r = await c.get(f"{API}/videos", params={"part": "snippet,statistics", "id": ",".join(ids[i:i + 50]), "key": key})
        r.raise_for_status()
        for v in r.json().get("items", []):
            pub = v["snippet"]["publishedAt"][:10]
            out.append({"video_id": v["id"], "channel": channel, "title": v["snippet"]["title"], "published_at": pub,
                        "views": int(v.get("statistics", {}).get("viewCount", 0)), "era": era_for_year(int(pub[:4]))})
    return out


async def main(handles: list[str], limit: int) -> None:
    s = get_settings()
    assert s.youtube_api_key, "YOUTUBE_API_KEY missing"
    videos: list[dict] = []
    async with httpx.AsyncClient(timeout=20) as c:
        for h in handles:
            title, uploads = await channel_uploads(c, s.youtube_api_key, h)
            ids = await playlist_video_ids(c, s.youtube_api_key, uploads, limit)
            got = await video_details(c, s.youtube_api_key, ids, title)
            print(f"{title}: {len(got)} videos")
            videos += got
    seed = json.loads(s.lore_seed_path.read_text(encoding="utf-8"))
    merged = {v["video_id"]: v for v in seed.get("video_index", []) if v.get("video_id") != "REPLACE_ME"}
    merged.update({v["video_id"]: v for v in videos})
    seed["video_index"] = sorted(merged.values(), key=lambda v: -v["views"])
    chans = set(seed.get("faze_channels", [])) | {v["channel"] for v in videos}
    seed["faze_channels"] = sorted(chans)
    s.lore_seed_path.write_text(json.dumps(seed, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"video_index now {len(seed['video_index'])} videos; top: {seed['video_index'][0]['title']!r} "
          f"({seed['video_index'][0]['views']:,} views)")
    if s.has_mongo:
        from motor.motor_asyncio import AsyncIOMotorClient
        db = AsyncIOMotorClient(s.mongodb_uri)[s.mongodb_db]
        for v in videos:
            await db.video_index.replace_one({"video_id": v["video_id"]}, v, upsert=True)
        print("upserted into Atlas video_index")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--handle", action="append", default=None)
    ap.add_argument("--max", type=int, default=200)
    a = ap.parse_args()
    asyncio.run(main(a.handle or ["@FaZeClan"], a.max))

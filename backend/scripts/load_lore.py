"""Embed lore_seed.json with Gemini and upsert into MongoDB Atlas.
Usage (from backend/):  python -m scripts.load_lore
Then create the vector index in Atlas (see scripts/atlas_vector_index.json)."""
import asyncio
import json

from motor.motor_asyncio import AsyncIOMotorClient

from app.config import get_settings
from app.services import gemini
from app.services.lore import entry_text


async def main() -> None:
    s = get_settings()
    assert s.has_mongo, "MONGODB_URI missing"
    assert s.has_gemini, "GEMINI_API_KEY missing (needed for embeddings)"
    seed = json.loads(s.lore_seed_path.read_text(encoding="utf-8"))
    entries = seed["lore_entries"]
    vecs = await gemini.embed([entry_text(e) for e in entries], timeout=60)
    assert vecs, "embedding failed"
    db = AsyncIOMotorClient(s.mongodb_uri)[s.mongodb_db]
    for e, v in zip(entries, vecs):
        await db.lore_entries.replace_one({"id": e["id"]}, {**e, "embedding": v}, upsert=True)
    vids = [v for v in seed.get("video_index", []) if v.get("video_id") != "REPLACE_ME"]
    for v in vids:
        await db.video_index.replace_one({"video_id": v["video_id"]}, v, upsert=True)
    print(f"upserted {len(entries)} lore entries ({len(vecs[0])}-dim) and {len(vids)} videos into {s.mongodb_db}")


if __name__ == "__main__":
    asyncio.run(main())

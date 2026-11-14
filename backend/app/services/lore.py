"""Lore retrieval (the RAG half of the Bard).

Primary: MongoDB Atlas Vector Search over `lore_entries.embedding`.
Fallback: the local seed JSON with in-memory cosine (if Gemini embeddings work)
or keyword scoring (if nothing works). Same interface either way."""
import json
import logging
import math
import re
from typing import Optional

from app.config import get_settings
from app.services import gemini

log = logging.getLogger("ithaca.lore")


def entry_text(e: dict) -> str:
    return f"{e['title']} ({e['year']}, {e['era']}). People: {', '.join(e.get('people', []))}. {e['summary']} {e['why_it_matters']}"


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


class LoreStore:
    def __init__(self) -> None:
        self.s = get_settings()
        seed = json.loads(self.s.lore_seed_path.read_text(encoding="utf-8"))
        self.entries: list[dict] = seed["lore_entries"]
        self.by_id = {e["id"]: e for e in self.entries}
        self.video_index: list[dict] = [v for v in seed.get("video_index", []) if v.get("video_id") != "REPLACE_ME"]
        self.faze_channels: list[str] = seed.get("faze_channels", [])
        self._local_vecs: Optional[list[list[float]]] = None
        self._mongo = None
        self.backend = "keyword"

    async def init(self) -> None:
        if self.s.has_mongo:
            try:
                from motor.motor_asyncio import AsyncIOMotorClient

                cli = AsyncIOMotorClient(self.s.mongodb_uri, serverSelectionTimeoutMS=4000)
                db = cli[self.s.mongodb_db]
                await db.command("ping")
                self._mongo = db
                n = await db.lore_entries.count_documents({})
                if n:
                    docs = await db.lore_entries.find({}, {"embedding": 0, "_id": 0}).to_list(500)
                    self.entries = docs
                    self.by_id = {e["id"]: e for e in docs}
                    vids = await db.video_index.find({}, {"_id": 0}).to_list(5000)
                    if vids:
                        self.video_index = vids
                self.backend = "atlas"
                log.info("lore: Atlas connected (%d entries)", n)
                return
            except Exception as e:
                log.warning("lore: Atlas unavailable, falling back: %r", e)
        vecs = await gemini.embed([entry_text(e) for e in self.entries])
        if vecs:
            self._local_vecs = vecs
            self.backend = "local-vector"
        log.info("lore backend: %s", self.backend)

    async def search(self, query: str, *, era: Optional[str] = None, k: int = 4) -> list[dict]:
        if self.backend == "atlas":
            qv = await gemini.embed([query], task="RETRIEVAL_QUERY")
            if qv:
                stage: dict = {
                    "index": self.s.atlas_vector_index,
                    "path": "embedding",
                    "queryVector": qv[0],
                    "numCandidates": 100,
                    "limit": k,
                }
                if era:
                    stage["filter"] = {"era": era}
                try:
                    docs = await self._mongo.lore_entries.aggregate([
                        {"$vectorSearch": stage},
                        {"$project": {"embedding": 0, "_id": 0, "score": {"$meta": "vectorSearchScore"}}},
                    ]).to_list(k)
                    if docs:
                        return docs
                except Exception as e:
                    log.warning("atlas vector search failed: %r", e)

        pool = [e for e in self.entries if not era or e["era"] == era] or self.entries
        if self.backend == "local-vector" and self._local_vecs:
            qv = await gemini.embed([query], task="RETRIEVAL_QUERY")
            if qv:
                idx = {e["id"]: i for i, e in enumerate(self.entries)}
                ranked = sorted(pool, key=lambda e: -_cos(qv[0], self._local_vecs[idx[e["id"]]]))
                return ranked[:k]
        q = _tokens(query)
        ranked = sorted(pool, key=lambda e: (-len(q & _tokens(entry_text(e))), e["year"]))
        return ranked[:k]

    def for_era(self, era: str) -> list[dict]:
        return sorted([e for e in self.entries if e["era"] == era], key=lambda e: e["year"])

    def at_timestamp(self, video_id: str, t: int) -> Optional[dict]:
        hits = [e for e in self.entries if e.get("video_id") == video_id]
        if not hits:
            return None
        inside = [e for e in hits if e.get("start_s", 0) <= t and (e.get("end_s") is None or t <= e["end_s"])]
        pool = inside or hits
        return max(pool, key=lambda e: e.get("start_s", 0) if e.get("start_s", 0) <= t else -1)

    def video_meta(self, video_id: str) -> Optional[dict]:
        return next((v for v in self.video_index if v["video_id"] == video_id), None)


_store: Optional[LoreStore] = None


def lore() -> LoreStore:
    global _store
    if _store is None:
        _store = LoreStore()
    return _store

"""Fans / events / relics / Drachmae. Tiger Data (asyncpg) when TIGER_DSN is set,
otherwise an in-memory store with seeded, clearly-labeled simulated history."""
import hashlib
import hmac
import json
import logging
import random
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.config import get_settings
from app.schemas import ERAS

log = logging.getLogger("ithaca.store")

DRACHMAE = {"omen": 50, "relic": 25, "watch": 1, "trial_entry": 50, "oracle_argos": 40, "onboard": 100, "episode_play": 10}
PRICES = {"odyssey_pass": 499, "era_drop": 3500, "sponsored_trial": 250000}


DEFAULT_TRIAL_PROMPT = "String the bow: show the Oracle your cleanest trickshot."
SUITORS = ["Antinous", "Eurymachus", "Amphinomus", "Ctesippus", "Leodes"]
DEMO_FAN_ID = "demo_odysseus"


def week_start():
    d = datetime.now(timezone.utc).date()
    return d - timedelta(days=d.weekday())


async def seed_demo_fan(st) -> None:
    """A ready-made returning fan for the demo (fan_id=demo_odysseus)."""
    if await st.get_fan(DEMO_FAN_ID) and (await st.get_fan(DEMO_FAN_ID)).get("path"):
        return
    await st.upsert_fan(DEMO_FAN_ID, handle="Odysseus")
    await st.update_fan(DEMO_FAN_ID, path="odysseus", entry_era="2013_rug_era", games=["Warzone", "Fortnite"])
    # first relic of the 2010 era and of the Rug era, whatever lore file is loaded
    cat = relic_catalog().values()
    picks = [next((r["id"] for r in cat if r["era"] == era), None) for era in ("2010_trickshots", "2013_rug_era")]
    for rid in [p for p in picks if p]:
        relic, already = await st.grant_relic(DEMO_FAN_ID, rid, via="seed")
        if relic and not already:
            await st.log_event(DEMO_FAN_ID, "relic", "web", {"era": relic["era"], "relic_id": rid})
    await st.add_drachmae(DEMO_FAN_ID, 340)


def now() -> datetime:
    return datetime.now(timezone.utc)


def hash_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    digits = "".join(ch for ch in phone if ch.isdigit())
    # keyed (HMAC), not plain SHA-256: phone numbers are too few to hide behind an unkeyed hash
    return hmac.new(get_settings().token_secret.encode(), digits.encode(), hashlib.sha256).hexdigest()


def relic_catalog() -> dict[str, dict]:
    from app.services.lore import lore

    out = {}
    for e in lore().entries:
        r = e.get("relic")
        if r:
            out[r["id"]] = {**r, "era": e["era"], "lore_id": e["id"], "art_url": r.get("art_url")}
    return out


# ------------------------------------------------------------------ memory
class MemoryStore:
    kind = "memory"

    def __init__(self) -> None:
        self.fans: dict[str, dict] = {}
        self.events: list[dict] = []
        self.fan_relics: dict[str, dict[str, dict]] = defaultdict(dict)
        self.purchases: list[dict] = []
        self.trials: dict[str, dict] = {}
        self.trial_entries: list[dict] = []

    async def init(self) -> None:
        self._simulate_history()
        await seed_demo_fan(self)

    # ---- trials (the Bow Trial + Suitors leaderboard)
    async def current_trial(self) -> dict:
        week = week_start()
        tid = f"trial_{week.isoformat()}"
        if tid not in self.trials:
            self.trials[tid] = {"id": tid, "week": week.isoformat(), "sponsor": None, "prompt": DEFAULT_TRIAL_PROMPT}
        return self.trials[tid]

    async def set_trial(self, sponsor: Optional[str], prompt: Optional[str]) -> dict:
        t = await self.current_trial()
        if sponsor is not None:
            t["sponsor"] = sponsor or None
        if prompt:
            t["prompt"] = prompt
        return t

    async def add_trial_entry(self, trial_id: str, fan_id: str, score: int, verdict: str, clip_url: Optional[str] = None) -> None:
        self.trial_entries.append({"trial_id": trial_id, "fan_id": fan_id, "score": score, "verdict": verdict,
                                   "clip_url": clip_url, "ts": now()})

    async def leaderboard(self, trial_id: str, limit: int = 10) -> list[dict]:
        best: dict[str, dict] = {}
        for e in self.trial_entries:
            if e["trial_id"] == trial_id and (e["fan_id"] not in best or e["score"] > best[e["fan_id"]]["score"]):
                best[e["fan_id"]] = e
        rows = sorted(best.values(), key=lambda e: (-e["score"], e["ts"]))[:limit]
        out = []
        for i, e in enumerate(rows, 1):
            f = self.fans.get(e["fan_id"], {})
            out.append({"rank": i, "fan_id": e["fan_id"], "handle": f.get("handle") or e["fan_id"], "score": e["score"],
                        "verdict": e["verdict"], "simulated": bool(f.get("simulated")),
                        "path": f.get("path"), "drachmae": f.get("drachmae", 0)})
        return out

    async def set_pass(self, fan_id: str) -> None:
        f = await self.upsert_fan(fan_id)
        f["has_pass"] = True

    async def get_fan(self, fan_id: str) -> Optional[dict]:
        return self.fans.get(fan_id)

    async def upsert_fan(self, fan_id: Optional[str], handle: Optional[str] = None, phone: Optional[str] = None) -> dict:
        ph = hash_phone(phone)
        if not fan_id and ph:
            fan_id = next((f["id"] for f in self.fans.values() if f["phone_hash"] == ph), None)
        fan_id = fan_id or f"fan_{uuid.uuid4().hex[:10]}"
        f = self.fans.get(fan_id) or {"id": fan_id, "handle": None, "phone_hash": None, "path": None,
                                       "entry_era": None, "games": [], "drachmae": 0, "has_pass": False,
                                       "created_at": now().isoformat()}
        if handle:
            f["handle"] = handle
        if ph:
            f["phone_hash"] = ph
        self.fans[fan_id] = f
        return f

    async def update_fan(self, fan_id: str, **fields) -> dict:
        f = await self.upsert_fan(fan_id)
        f.update({k: v for k, v in fields.items() if v is not None})
        return f

    async def add_drachmae(self, fan_id: str, n: int) -> int:
        f = await self.upsert_fan(fan_id)
        f["drachmae"] += n
        return f["drachmae"]

    async def log_event(self, fan_id: Optional[str], type_: str, source: str, meta: Optional[dict] = None, ts: Optional[datetime] = None) -> None:
        self.events.append({"ts": ts or now(), "fan_id": fan_id, "type": type_, "source": source, "meta": meta or {}})

    async def grant_relic(self, fan_id: str, relic_id: str, via: str) -> tuple[Optional[dict], bool]:
        cat = relic_catalog()
        r = cat.get(relic_id)
        if not r:
            return None, False
        await self.upsert_fan(fan_id)
        if relic_id in self.fan_relics[fan_id]:
            return {**r, **self.fan_relics[fan_id][relic_id]}, True
        rec = {"earned_at": now().isoformat(), "via": via}
        self.fan_relics[fan_id][relic_id] = rec
        return {**r, **rec}, False

    async def delete_fan_data(self, fan_id: str) -> dict:
        """Erase one fan's data (privacy request). Returns how many rows went."""
        before = (len(self.events), len(self.trial_entries), len(self.purchases))
        self.events = [e for e in self.events if e.get("fan_id") != fan_id]
        self.trial_entries = [e for e in self.trial_entries if e.get("fan_id") != fan_id]
        self.purchases = [p for p in self.purchases if p.get("fan_id") != fan_id]
        relics = len(self.fan_relics.pop(fan_id, {}))
        return {"fan": self.fans.pop(fan_id, None) is not None, "relics": relics,
                "events": before[0] - len(self.events), "trial_entries": before[1] - len(self.trial_entries),
                "purchases": before[2] - len(self.purchases)}

    async def fan_event_kinds(self, fan_id: str) -> set[tuple[str, str]]:
        """Distinct (type, source) pairs this fan has generated: powers Athena's quest."""
        return {(e["type"], e["source"]) for e in self.events if e["fan_id"] == fan_id}

    async def list_fan_relics(self, fan_id: str) -> list[dict]:
        cat = relic_catalog()
        return [{**cat[rid], **rec} for rid, rec in self.fan_relics.get(fan_id, {}).items() if rid in cat]

    async def record_purchase(self, fan_id: Optional[str], sku: str, amount_cents: int, ts: Optional[datetime] = None) -> None:
        self.purchases.append({"fan_id": fan_id, "sku": sku, "amount_cents": amount_cents, "ts": ts or now()})

    async def metrics(self, days: int = 14) -> dict:
        start = (now() - timedelta(days=days - 1)).date()
        daily = {start + timedelta(days=i): {"active": set(), "reactivated": set(), "new_fans": set(), "trial_entries": 0,
                                               "relics": 0, "episodes": 0, "sponsored_impressions": 0}
                 for i in range(days)}
        era_demand = defaultdict(int)
        for e in self.events:
            d = e["ts"].date()
            if d not in daily:
                continue
            b = daily[d]
            if e["fan_id"]:
                b["active"].add(e["fan_id"])
            t = e["type"]
            if t == "onboard":
                (b["reactivated"] if e["meta"].get("path") == "odysseus" else b["new_fans"]).add(e["fan_id"])
            elif t == "trial_entry":
                b["trial_entries"] += 1
            elif t == "relic":
                b["relics"] += 1
                if e["meta"].get("era"):
                    era_demand[e["meta"]["era"]] += 1
            elif t == "episode_play":
                b["episodes"] += 1
            elif t == "sponsored_impression":
                b["sponsored_impressions"] += 1
        rows = [{"day": d.isoformat(), "active_fans": len(b["active"]), "reactivated": len(b["reactivated"]),
                 "new_fans": len(b["new_fans"]), "trial_entries": b["trial_entries"], "relics": b["relics"],
                 "episodes": b["episodes"], "sponsored_impressions": b["sponsored_impressions"]}
                for d, b in sorted(daily.items())]
        rev = defaultdict(int)
        passes = 0
        day_rev: dict[str, dict] = defaultdict(lambda: defaultdict(int))
        for p in self.purchases:
            stream = p["sku"].split(":")[0]
            rev[stream] += p["amount_cents"]
            passes += stream == "odyssey_pass"
            if p["ts"].date() in daily:
                day_rev[p["ts"].date().isoformat()][stream] += p["amount_cents"]
        for r in rows:
            dr = day_rev.get(r["day"], {})
            r.update(pass_cents=dr.get("odyssey_pass", 0), drops_cents=dr.get("era_drop", 0), sponsored_cents=dr.get("sponsored_trial", 0))
        by_type: dict[str, set] = defaultdict(set)
        for e in self.events:
            if e["fan_id"] and e["ts"].date() in daily:
                by_type[e["type"]].add(e["fan_id"])
        buyers = {p["fan_id"] for p in self.purchases if p["fan_id"] and p["sku"] == "odyssey_pass" and p["ts"].date() in daily}
        funnel = _funnel(len(by_type["onboard"]), len(by_type["episode_play"]), len(by_type["relic"]),
                         len(by_type["trial_entry"]), len(buyers))
        return _assemble(rows, dict(rev), passes, dict(era_demand), len(self.fans), simulated=True, backend=self.kind, funnel=funnel)

    # simulated history so the War Room isn't empty (labelled simulated=True)
    def _simulate_history(self, days: int = 14, seed: int = 7) -> None:
        rng = random.Random(seed)
        tid = f"trial_{week_start().isoformat()}"
        for j, name in enumerate(SUITORS):
            fid = f"sim_suitor_{j}"
            self.fans[fid] = {"id": fid, "handle": name, "phone_hash": None, "path": "telemachus", "entry_era": "today",
                              "games": [], "drachmae": 0, "has_pass": False, "created_at": now().isoformat(), "simulated": True}
            self.trial_entries.append({"trial_id": tid, "fan_id": fid, "score": 88 - j * 6 + rng.randint(-2, 2),
                                       "verdict": "simulated suitor", "clip_url": None, "ts": now() - timedelta(hours=j + 1)})
        cat = list(relic_catalog().values())
        t0 = now() - timedelta(days=days - 1)
        fan_seq = 0
        for i in range(days):
            day = t0 + timedelta(days=i)
            growth = 1 + i * 0.12
            for _ in range(int(rng.randint(18, 26) * growth)):
                fan_seq += 1
                fid = f"sim_{fan_seq}"
                path = "odysseus" if rng.random() < 0.58 else "telemachus"
                era = rng.choice(ERAS[:4]) if path == "odysseus" else "today"
                self.fans[fid] = {"id": fid, "handle": None, "phone_hash": None, "path": path, "entry_era": era,
                                  "games": [], "drachmae": 0, "created_at": day.isoformat(), "simulated": True}
                ts = day + timedelta(minutes=rng.randint(0, 1400))
                self.events.append({"ts": ts, "fan_id": fid, "type": "onboard", "source": rng.choice(["web", "facetime"]),
                                    "meta": {"path": path, "era": era, "simulated": True}})
                for _ in range(rng.randint(1, 4)):
                    r = rng.choice(cat)
                    self.events.append({"ts": ts + timedelta(minutes=rng.randint(1, 600)), "fan_id": fid, "type": "relic",
                                        "source": rng.choice(["ext", "facetime", "web"]), "meta": {"era": r["era"], "simulated": True}})
                if rng.random() < 0.6:
                    self.events.append({"ts": ts, "fan_id": fid, "type": "episode_play", "source": "web", "meta": {"simulated": True}})
                if rng.random() < 0.3:
                    self.events.append({"ts": ts, "fan_id": fid, "type": "trial_entry", "source": "facetime",
                                        "meta": {"score": rng.randint(40, 98), "simulated": True}})
                if rng.random() < 0.07:
                    self.purchases.append({"fan_id": fid, "sku": "odyssey_pass", "amount_cents": PRICES["odyssey_pass"], "ts": ts})
                if rng.random() < 0.02:
                    self.purchases.append({"fan_id": fid, "sku": f"era_drop:{era}", "amount_cents": PRICES["era_drop"], "ts": ts})
            for _ in range(int(rng.randint(300, 500) * growth)):
                self.events.append({"ts": day + timedelta(minutes=rng.randint(0, 1400)), "fan_id": None,
                                    "type": "sponsored_impression", "source": "web", "meta": {"simulated": True}})
            if i % 7 == 0:
                self.purchases.append({"fan_id": None, "sku": "sponsored_trial:demo_brand",
                                       "amount_cents": PRICES["sponsored_trial"], "ts": day})


# ------------------------------------------------------------------ postgres
class PgStore(MemoryStore):
    kind = "tiger"

    def __init__(self, dsn: str) -> None:
        super().__init__()
        self.dsn = dsn
        self.pool = None

    async def init(self) -> None:
        import asyncpg

        self.pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=5, command_timeout=8,
                                              init=lambda c: c.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"))
        async with self.pool.acquire() as c:
            await c.execute("ALTER TABLE fans ADD COLUMN IF NOT EXISTS has_pass BOOLEAN NOT NULL DEFAULT false")
            for r in relic_catalog().values():
                await c.execute("INSERT INTO relics(id, era, name, rarity, art_url) VALUES($1,$2,$3,$4,$5) "
                                "ON CONFLICT (id) DO UPDATE SET era=EXCLUDED.era, name=EXCLUDED.name, rarity=EXCLUDED.rarity",
                                r["id"], r["era"], r["name"], r["rarity"], r.get("art_url"))
        await seed_demo_fan(self)
        # A fresh Tiger DB (e.g. Render) gets the labelled simulated history once, so the War Room isn't all zeros.
        try:
            async with self.pool.acquire() as c:
                empty = not await c.fetchval("SELECT 1 FROM events WHERE meta->>'simulated'='true' LIMIT 1")
            if empty:
                log.info("Tiger has no simulated history: %s", await self.seed_simulated())
        except Exception as e:
            log.warning("simulated history seed failed (%r); War Room will show live data only", e)

    async def seed_simulated(self) -> str:
        """Replace the simulated history (meta.simulated=true) with a fresh 14-day copy. Real fan data is untouched."""
        mem = MemoryStore()
        mem._simulate_history()
        async with self.pool.acquire() as c, c.transaction():
            await c.execute("DELETE FROM events WHERE meta->>'simulated'='true'")
            await c.execute("DELETE FROM purchases WHERE fan_id LIKE 'sim_%' "
                            "OR (fan_id IS NULL AND sku='sponsored_trial:demo_brand')")  # the sim's sponsor rows
            await c.executemany(
                "INSERT INTO fans(id, path, entry_era, created_at) VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING",
                [(f["id"], f["path"], f["entry_era"], datetime.fromisoformat(f["created_at"])) for f in mem.fans.values()])
            await c.copy_records_to_table("events", records=[(e["ts"], e["fan_id"], e["type"], e["source"], e["meta"])
                                                             for e in mem.events], columns=["ts", "fan_id", "type", "source", "meta"])
            await c.executemany("INSERT INTO purchases(fan_id, sku, amount_cents, ts) VALUES($1,$2,$3,$4)",
                                [(p["fan_id"], p["sku"], p["amount_cents"], p["ts"]) for p in mem.purchases])
            trial = await self.current_trial()
            await c.execute("DELETE FROM trial_entries WHERE fan_id LIKE 'sim_%'")
            await c.executemany("INSERT INTO trial_entries(trial_id, fan_id, score, verdict, ts) VALUES($1,$2,$3,$4,$5)",
                                [(trial["id"], e["fan_id"], e["score"], e["verdict"], e["ts"]) for e in mem.trial_entries])
            await c.executemany("UPDATE fans SET handle=$2 WHERE id=$1",
                                [(f["id"], f["handle"]) for f in mem.fans.values() if f.get("handle")])
        return f"seeded {len(mem.fans)} sim fans, {len(mem.events)} events, {len(mem.purchases)} purchases"

    async def current_trial(self) -> dict:
        week = week_start()
        tid = f"trial_{week.isoformat()}"
        async with self.pool.acquire() as c:
            await c.execute("INSERT INTO trials(id, week, prompt) VALUES($1,$2,$3) ON CONFLICT DO NOTHING", tid, week, DEFAULT_TRIAL_PROMPT)
            r = dict(await c.fetchrow("SELECT * FROM trials WHERE id=$1", tid))
        r["week"] = r["week"].isoformat()
        return r

    async def set_trial(self, sponsor, prompt) -> dict:
        t = await self.current_trial()
        async with self.pool.acquire() as c:
            await c.execute("UPDATE trials SET sponsor=COALESCE($2, sponsor), prompt=COALESCE($3, prompt) WHERE id=$1",
                            t["id"], sponsor, prompt or None)
        return await self.current_trial()

    async def add_trial_entry(self, trial_id, fan_id, score, verdict, clip_url=None) -> None:
        async with self.pool.acquire() as c:
            await c.execute("INSERT INTO trial_entries(trial_id, fan_id, score, verdict, clip_url) VALUES($1,$2,$3,$4,$5)",
                            trial_id, fan_id, score, verdict, clip_url)

    async def leaderboard(self, trial_id: str, limit: int = 10) -> list[dict]:
        async with self.pool.acquire() as c:
            rows = await c.fetch("""
                SELECT DISTINCT ON (te.fan_id) te.fan_id, te.score, te.verdict, te.ts, f.handle, f.path, f.drachmae
                FROM trial_entries te LEFT JOIN fans f ON f.id = te.fan_id
                WHERE te.trial_id=$1 ORDER BY te.fan_id, te.score DESC, te.ts""", trial_id)
        rows = sorted(rows, key=lambda r: (-(r["score"] or 0), r["ts"]))[:limit]
        return [{"rank": i, "fan_id": r["fan_id"], "handle": r["handle"] or r["fan_id"], "score": r["score"],
                 "verdict": r["verdict"], "simulated": r["fan_id"].startswith("sim_"),
                 "path": r["path"], "drachmae": r["drachmae"] or 0} for i, r in enumerate(rows, 1)]

    async def set_pass(self, fan_id: str) -> None:
        await self.upsert_fan(fan_id)
        async with self.pool.acquire() as c:
            await c.execute("UPDATE fans SET has_pass=true WHERE id=$1", fan_id)

    @staticmethod
    def _fan(row) -> Optional[dict]:
        if not row:
            return None
        d = dict(row)
        d["games"] = list(d.get("games") or [])
        d["created_at"] = d["created_at"].isoformat()
        return d

    async def get_fan(self, fan_id: str) -> Optional[dict]:
        async with self.pool.acquire() as c:
            return self._fan(await c.fetchrow("SELECT * FROM fans WHERE id=$1", fan_id))

    async def upsert_fan(self, fan_id: Optional[str], handle: Optional[str] = None, phone: Optional[str] = None) -> dict:
        ph = hash_phone(phone)
        async with self.pool.acquire() as c:
            if not fan_id and ph:
                fan_id = await c.fetchval("SELECT id FROM fans WHERE phone_hash=$1", ph)
            fan_id = fan_id or f"fan_{uuid.uuid4().hex[:10]}"
            row = await c.fetchrow(
                "INSERT INTO fans(id, handle, phone_hash) VALUES($1,$2,$3) ON CONFLICT (id) DO UPDATE SET "
                "handle=COALESCE(EXCLUDED.handle, fans.handle), phone_hash=COALESCE(EXCLUDED.phone_hash, fans.phone_hash) RETURNING *",
                fan_id, handle, ph)
            return self._fan(row)

    async def update_fan(self, fan_id: str, **fields) -> dict:
        await self.upsert_fan(fan_id)
        fields = {k: v for k, v in fields.items() if v is not None and k in {"path", "entry_era", "games", "handle"}}
        if fields:
            sets = ", ".join(f"{k}=${i + 2}" for i, k in enumerate(fields))
            async with self.pool.acquire() as c:
                await c.execute(f"UPDATE fans SET {sets} WHERE id=$1", fan_id, *fields.values())
        return await self.get_fan(fan_id)

    async def add_drachmae(self, fan_id: str, n: int) -> int:
        await self.upsert_fan(fan_id)
        async with self.pool.acquire() as c:
            return await c.fetchval("UPDATE fans SET drachmae=drachmae+$2 WHERE id=$1 RETURNING drachmae", fan_id, n)

    async def log_event(self, fan_id, type_, source, meta=None, ts=None) -> None:
        async with self.pool.acquire() as c:
            await c.execute("INSERT INTO events(ts, fan_id, type, source, meta) VALUES($1,$2,$3,$4,$5)",
                            ts or now(), fan_id, type_, source, meta or {})

    async def grant_relic(self, fan_id: str, relic_id: str, via: str):
        r = relic_catalog().get(relic_id)
        if not r:
            return None, False
        await self.upsert_fan(fan_id)
        async with self.pool.acquire() as c:
            row = await c.fetchrow("INSERT INTO fan_relics(fan_id, relic_id, via) VALUES($1,$2,$3) "
                                   "ON CONFLICT DO NOTHING RETURNING earned_at, via", fan_id, relic_id, via)
            already = row is None
            if already:
                row = await c.fetchrow("SELECT earned_at, via FROM fan_relics WHERE fan_id=$1 AND relic_id=$2", fan_id, relic_id)
        return {**r, "earned_at": row["earned_at"].isoformat(), "via": row["via"]}, already

    async def fan_event_kinds(self, fan_id: str) -> set[tuple[str, str]]:
        async with self.pool.acquire() as c:
            rows = await c.fetch("SELECT DISTINCT type, source FROM events WHERE fan_id=$1", fan_id)
        return {(r["type"], r["source"]) for r in rows}

    async def delete_fan_data(self, fan_id: str) -> dict:
        """Erase one fan's rows in Tiger Data, child tables first (privacy request)."""
        out = {}
        async with self.pool.acquire() as c:
            async with c.transaction():
                for table, key in (("fan_relics", "relics"), ("trial_entries", "trial_entries"),
                                   ("events", "events"), ("purchases", "purchases"), ("fans", "fan")):
                    col = "id" if table == "fans" else "fan_id"
                    status = await c.execute(f"DELETE FROM {table} WHERE {col}=$1", fan_id)
                    out[key] = int(status.split()[-1])
        out["fan"] = bool(out.pop("fan"))
        return out



    async def list_fan_relics(self, fan_id: str) -> list[dict]:
        cat = relic_catalog()
        async with self.pool.acquire() as c:
            rows = await c.fetch("SELECT relic_id, earned_at, via FROM fan_relics WHERE fan_id=$1 ORDER BY earned_at", fan_id)
        return [{**cat[r["relic_id"]], "earned_at": r["earned_at"].isoformat(), "via": r["via"]} for r in rows if r["relic_id"] in cat]

    async def record_purchase(self, fan_id, sku, amount_cents, ts=None) -> None:
        async with self.pool.acquire() as c:
            await c.execute("INSERT INTO purchases(fan_id, sku, amount_cents, ts) VALUES($1,$2,$3,$4)", fan_id, sku, amount_cents, ts or now())

    async def metrics(self, days: int = 14) -> dict:
        since = now() - timedelta(days=days - 1)
        async with self.pool.acquire() as c:
            eng = {r["day"].date(): dict(r) for r in await c.fetch("SELECT * FROM daily_engagement WHERE day >= $1", since)}
            rea = {r["day"].date(): dict(r) for r in await c.fetch("SELECT * FROM reactivated_fans_daily WHERE day >= $1", since)}
            tri = {r["day"].date(): dict(r) for r in await c.fetch("SELECT * FROM trial_entries_daily WHERE day >= $1", since)}
            rev = {r["stream"]: r["cents"] for r in await c.fetch(
                "SELECT split_part(sku, ':', 1) AS stream, sum(amount_cents)::bigint AS cents FROM purchases WHERE ts >= $1 GROUP BY 1", since)}
            passes = await c.fetchval("SELECT count(*) FROM purchases WHERE sku='odyssey_pass' AND ts >= $1", since)
            era = {r["era"]: r["n"] for r in await c.fetch(
                "SELECT meta->>'era' AS era, count(*) AS n FROM events WHERE type='relic' AND ts >= $1 AND meta ? 'era' GROUP BY 1", since)}
            fans = await c.fetchval("SELECT count(*) FROM fans")
            day_rev = {}
            for r in await c.fetch("SELECT date_trunc('day', ts)::date AS d, split_part(sku, ':', 1) AS stream, sum(amount_cents)::bigint AS cents "
                                   "FROM purchases WHERE ts >= $1 GROUP BY 1, 2", since):
                day_rev.setdefault(r["d"].isoformat(), {})[r["stream"]] = int(r["cents"])
            ft = {r["type"]: r["n"] for r in await c.fetch(
                "SELECT type, count(DISTINCT fan_id) AS n FROM events WHERE ts >= $1 AND fan_id IS NOT NULL GROUP BY 1", since)}
            buyers = await c.fetchval("SELECT count(DISTINCT fan_id) FROM purchases WHERE sku='odyssey_pass' AND ts >= $1", since)
            simulated = await c.fetchval("SELECT EXISTS(SELECT 1 FROM events WHERE meta->>'simulated'='true' AND ts >= $1)", since)
        start = since.date()
        rows = []
        for i in range(days):
            d = start + timedelta(days=i)
            e, r, t = eng.get(d, {}), rea.get(d, {}), tri.get(d, {})
            rows.append({"day": d.isoformat(), "active_fans": e.get("active_fans", 0), "reactivated": r.get("reactivated", 0),
                         "new_fans": r.get("new_fans", 0), "trial_entries": t.get("trial_entries", 0), "relics": e.get("relics", 0),
                         "episodes": e.get("episodes", 0), "sponsored_impressions": e.get("sponsored_impressions", 0)})
        for r in rows:
            dr = day_rev.get(r["day"], {})
            r.update(pass_cents=dr.get("odyssey_pass", 0), drops_cents=dr.get("era_drop", 0), sponsored_cents=dr.get("sponsored_trial", 0))
        funnel = _funnel(ft.get("onboard", 0), ft.get("episode_play", 0), ft.get("relic", 0), ft.get("trial_entry", 0), buyers)
        return _assemble(rows, {k: int(v) for k, v in rev.items()}, passes, era, fans, simulated=bool(simulated), backend=self.kind,
                         funnel=funnel)



def _funnel(onboarded, episodes, relics, trials, passes) -> list[dict]:
    # ordered widest to narrowest so each step reads as a drop-off
    return [{"stage": "Onboarded with the Bard", "count": onboarded}, {"stage": "Collected a relic", "count": relics},
            {"stage": "Played a Bard episode", "count": episodes}, {"stage": "Entered a Bow Trial", "count": trials},
            {"stage": "Bought the Odyssey Pass", "count": passes}]


def _assemble(rows, rev, passes, era_demand, fans, *, simulated, backend, funnel=None) -> dict:
    tot = lambda k: sum(r[k] for r in rows)
    reactivated, new = tot("reactivated"), tot("new_fans")
    return {
        "simulated": simulated,
        "backend": backend,
        "generated_at": now().isoformat(),
        "funnel": funnel or [],
        "window_days": len(rows),
        "totals": {
            "fans": fans,
            "reactivated_fans": reactivated,
            "new_fans": new,
            "dau_today": rows[-1]["active_fans"] if rows else 0,
            "trial_entries": tot("trial_entries"),
            "relics_collected": tot("relics"),
            "episodes_played": tot("episodes"),
            "sponsored_impressions": tot("sponsored_impressions"),
            "pass_conversions": passes,
            "pass_conversion_rate": round(passes / max(1, reactivated + new), 4),
            "revenue_cents": sum(rev.values()),
        },
        "revenue_by_stream_cents": {
            "odyssey_pass": rev.get("odyssey_pass", 0),
            "era_drop": rev.get("era_drop", 0),
            "sponsored_trial": rev.get("sponsored_trial", 0),
        },
        "era_drop_demand": {e: era_demand.get(e, 0) for e in ERAS},
        "daily": rows,
    }


_store = None


def store() -> MemoryStore:
    global _store
    if _store is None:
        s = get_settings()
        _store = PgStore(s.tiger_dsn) if s.has_tiger else MemoryStore()
    return _store


async def init_store() -> None:
    global _store
    st = store()
    try:
        await st.init()
    except Exception as e:
        log.warning("Tiger unavailable (%r) -> in-memory store", e)
        _store = MemoryStore()
        await _store.init()


async def award(fan_id: str, type_: str, source: str, meta: Optional[dict] = None, drachmae: Optional[int] = None) -> int:
    """Log an event and pay Drachmae in one call. Returns new balance."""
    st = store()
    await st.log_event(fan_id, type_, source, meta)
    n = DRACHMAE.get(type_, 0) if drachmae is None else drachmae
    return await st.add_drachmae(fan_id, n) if n else (await st.get_fan(fan_id) or {}).get("drachmae", 0)

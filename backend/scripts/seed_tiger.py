"""Copy the simulated 14-day history (meta.simulated=true) into Tiger so the War Room charts
aren't empty. Usage (from backend/, after sql/schema.sql):  python -m scripts.seed_tiger"""
import asyncio
from datetime import datetime

import asyncpg

from app.config import get_settings
from app.services.lore import lore
from app.services.store import MemoryStore, PgStore


async def main() -> None:
    s = get_settings()
    assert s.has_tiger, "TIGER_DSN missing"
    await lore().init()
    mem = MemoryStore()
    mem._simulate_history()
    pg = PgStore(s.tiger_dsn)
    await pg.init()  # also upserts the relic catalog
    async with pg.pool.acquire() as c:
        await c.execute("DELETE FROM events WHERE meta->>'simulated'='true'")
        await c.executemany(
            "INSERT INTO fans(id, path, entry_era, created_at) VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING",
            [(f["id"], f["path"], f["entry_era"], datetime.fromisoformat(f["created_at"])) for f in mem.fans.values()])
        await c.copy_records_to_table("events", records=[(e["ts"], e["fan_id"], e["type"], e["source"], e["meta"])
                                                         for e in mem.events], columns=["ts", "fan_id", "type", "source", "meta"])
        await c.executemany("INSERT INTO purchases(fan_id, sku, amount_cents, ts) VALUES($1,$2,$3,$4)",
                            [(p["fan_id"], p["sku"], p["amount_cents"], p["ts"]) for p in mem.purchases])
        trial = await pg.current_trial()
        await c.execute("DELETE FROM trial_entries WHERE fan_id LIKE 'sim_%'")
        await c.executemany("INSERT INTO trial_entries(trial_id, fan_id, score, verdict, ts) VALUES($1,$2,$3,$4,$5)",
                            [(trial["id"], e["fan_id"], e["score"], e["verdict"], e["ts"]) for e in mem.trial_entries])
        await c.executemany("UPDATE fans SET handle=$2 WHERE id=$1",
                            [(f["id"], f["handle"]) for f in mem.fans.values() if f.get("handle")])
    print(f"seeded {len(mem.fans)} sim fans, {len(mem.events)} events, {len(mem.purchases)} purchases")


if __name__ == "__main__":
    asyncio.run(main())

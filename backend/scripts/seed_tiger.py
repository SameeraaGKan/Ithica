"""Re-copy the simulated 14-day history (meta.simulated=true) into Tiger so the War Room charts
aren't empty. The API also does this by itself on startup when Tiger has none.
Usage (from backend/, after sql/schema.sql):  python -m scripts.seed_tiger"""
import asyncio

from app.config import get_settings
from app.services.lore import lore
from app.services.store import PgStore


async def main() -> None:
    s = get_settings()
    assert s.has_tiger, "TIGER_DSN missing"
    await lore().init()
    pg = PgStore(s.tiger_dsn)
    await pg.init()  # also upserts the relic catalog, and seeds once if empty
    print(await pg.seed_simulated())


if __name__ == "__main__":
    asyncio.run(main())

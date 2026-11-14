"""Pre-generate + cache every era x path episode (audio included) before the demo.
Usage (from backend/):  python -m scripts.pregen_episodes"""
import asyncio

from app.schemas import ERAS
from app.services import bard
from app.services.lore import lore


async def main() -> None:
    await lore().init()
    bard.load_cache()
    for era in ERAS:
        for path in ("odysseus", "telemachus"):
            ep = await bard.episode(era=era, path=path)
            print(f"{era:16} {path:10} {ep.generated_by:8} audio={'yes' if ep.audio_url else 'no '} {ep.title}")


if __name__ == "__main__":
    asyncio.run(main())

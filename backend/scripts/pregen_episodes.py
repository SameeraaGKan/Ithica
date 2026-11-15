"""Pre-generate + cache every era x path episode (audio included) and the new-fan montage narration before the demo.
Usage (from backend/):  python -m scripts.pregen_episodes [--intro-only]"""
import asyncio

from app.schemas import ERAS
from app.services import bard, intro
from app.services.lore import lore


async def main() -> None:
    import sys
    await lore().init()
    bard.load_cache()
    # the montage first: 8 short lines, the most visible audio in the demo
    n = await intro.narration()
    voiced = sum(1 for x in n["lines"] if x["audio_url"])
    print(f"new-fan montage: {voiced}/{len(n['lines'])} lines voiced")
    if "--intro-only" in sys.argv:
        return
    for era in ERAS:
        for path in ("odysseus", "telemachus"):
            ep = await bard.episode(era=era, path=path)
            kind = ("elevenlabs" if ep.audio_url.endswith(".mp3") else "gemini" if ep.audio_url.endswith(".gem.wav")
                    else "built-in") if ep.audio_url else "none"
            print(f"{era:16} {path:10} {ep.generated_by:8} voice={kind:10} {ep.title}")


if __name__ == "__main__":
    asyncio.run(main())

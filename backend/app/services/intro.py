"""'FaZe in 40 seconds': the new-fan montage on the home page, narrated in the Bard's ElevenLabs voice.

One line per slide (same order as frontend/components/FazeMontage.tsx), plus the closing line. Facts come from
data/lore_seed.json. Audio is cached per line by tts.narrate, so after the first run (or scripts.pregen_episodes)
it's instant. No ElevenLabs = no audio_url, and the montage plays silent rather than in a robotic voice.
"""
import asyncio

from app.services import tts

LINES = [
    "Twenty ten. Three kids and a sniper rifle. CLipZ, House Cat and Resistance start a YouTube channel called "
    "FaZe Sniping, posting Call of Duty trickshots.",
    "Then came ILLCAMS. The trickshot montages exploded, and by twenty twelve FaZe had a million subscribers: "
    "one of the first giant gaming channels on YouTube.",
    "Twenty thirteen. Rug, Banks and Adapt turned gaming into a lifestyle. Vlogs, pranks, the FaZe House. "
    "By twenty eighteen, a hundred and sixteen million followers.",
    "And FaZe won. Counter-Strike in twenty sixteen. Call of Duty League champions in twenty twenty-one. "
    "And in twenty twenty-two, the first fully international roster to win a Counter-Strike Major.",
    "Twenty twenty. Swagg brought his Nuke Squad into FaZe, and more than two hundred and eleven thousand people "
    "applied to join through the FaZe Five challenge.",
    "Twenty twenty-two. Snoop Dogg joins FaZe, and the name travels far beyond gaming.",
    "And now, the founders have come home. Banks, Temperrr and Apex rebuild FaZe: a Six Invitational title in "
    "twenty twenty-six, and FaZe Up Next for the stars still to come.",
    "That's FaZe. Kids who turned clips into a culture. You missed some of it, Telemachus. Come, let's find the rest.",
]


async def narration() -> dict:
    urls = await asyncio.gather(*(tts.narrate(t, local_fallback=False) for t in LINES), return_exceptions=True)
    return {"voice": "bard",
            "lines": [{"text": t, "audio_url": u if isinstance(u, str) else None} for t, u in zip(LINES, urls)]}

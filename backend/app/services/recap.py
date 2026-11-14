"""Shareable "My FaZe Odyssey" recap (P1): vertical 1080x1920, 15s, four scenes with
crossfades, Bard narration underneath. Pillow draws the scenes, FFmpeg stitches them.
Cached by fan state, so re-requesting is instant until the fan earns something new."""
import asyncio
import hashlib
import logging
import shutil
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel

from app.config import get_settings
from app.schemas import ERA_LABELS, ERAS
from app.services import gemini, tts

log = logging.getLogger("ithaca.recap")

W, H = 1080, 1920
DUR = 15.0
SCENES = 4
FADE = 0.6
RED, GOLD, INK, CREAM, DIM = (228, 27, 35), (201, 162, 74), (11, 11, 12), (243, 239, 230), (90, 80, 70)
RARITY = {"legendary": GOLD, "epic": (170, 110, 230), "rare": (80, 150, 230), "common": (170, 170, 170)}

_FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu", "C:/Windows/Fonts", "/Library/Fonts"]


def _font(size: int, bold: bool = False, serif: bool = True) -> ImageFont.FreeTypeFont:
    names = (["DejaVuSerif-Bold.ttf", "georgiab.ttf"] if bold else ["DejaVuSerif.ttf", "georgia.ttf"]) if serif else \
            (["DejaVuSans-Bold.ttf", "arialbd.ttf"] if bold else ["DejaVuSans.ttf", "arial.ttf"])
    for d in _FONT_DIRS:
        for n in names:
            p = Path(d) / n
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default(size)


def _bg() -> Image.Image:
    im = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(im)
    for y in range(0, H, 4):  # subtle warm vertical gradient
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(26 * (1 - t) + 11 * t), int(18 * (1 - t) + 11 * t), int(20 * (1 - t) + 12 * t)), width=4)
    d.rectangle([40, 40, W - 40, H - 40], outline=(58, 45, 34), width=3)
    d.text((W // 2, 110), "I T H A C A", font=_font(44, serif=True), fill=GOLD, anchor="mm")
    d.text((W // 2, H - 100), "every fan's road home to FaZe", font=_font(30, serif=True), fill=DIM, anchor="mm")
    return im


def _wrap(d: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        nxt = f"{cur} {w}".strip()
        if d.textlength(nxt, font=font) <= width:
            cur = nxt
        else:
            lines.append(cur)
            cur = w
    return lines + ([cur] if cur else [])


def _scene_title(handle: str, path: str) -> Image.Image:
    im = _bg()
    d = ImageDraw.Draw(im)
    d.text((W // 2, 640), "MY FAZE", font=_font(120, bold=True), fill=CREAM, anchor="mm")
    d.text((W // 2, 790), "ODYSSEY", font=_font(150, bold=True), fill=RED, anchor="mm")
    role = "ODYSSEUS · the one who came home" if path == "odysseus" else "TELEMACHUS · the one who sought the legend"
    d.text((W // 2, 960), role, font=_font(38), fill=GOLD, anchor="mm")
    d.text((W // 2, 1150), f"@{handle}", font=_font(64, bold=True, serif=False), fill=CREAM, anchor="mm")
    return im


def _scene_map(entry: Optional[str], collected: dict[str, int]) -> Image.Image:
    im = _bg()
    d = ImageDraw.Draw(im)
    d.text((W // 2, 300), "THE VOYAGE", font=_font(72, bold=True), fill=CREAM, anchor="mm")
    top, step = 470, 270
    x = W // 2
    d.line([(x, top), (x, top + step * (len(ERAS) - 1))], fill=(70, 55, 40), width=6)
    for i, era in enumerate(ERAS):
        y = top + i * step
        is_entry = era == entry
        r = 46 if is_entry else 30
        d.ellipse([x - r, y - r, x + r, y + r], fill=RED if is_entry else (40, 32, 26), outline=GOLD, width=5)
        label = ERA_LABELS[era]
        side = -1 if i % 2 else 1
        tx = x + side * 80
        d.text((tx, y - 18), label, font=_font(40, bold=is_entry), fill=CREAM if is_entry else (200, 190, 175),
               anchor="lm" if side > 0 else "rm")
        n = collected.get(era, 0)
        sub = ("YOU WERE HERE · " if is_entry else "") + f"{n} relic{'' if n == 1 else 's'}"
        d.text((tx, y + 32), sub, font=_font(30, serif=False), fill=GOLD if is_entry else DIM, anchor="lm" if side > 0 else "rm")
    return im


def _scene_relics(relics: list[dict]) -> Image.Image:
    im = _bg()
    d = ImageDraw.Draw(im)
    d.text((W // 2, 300), "RELICS CLAIMED", font=_font(72, bold=True), fill=CREAM, anchor="mm")
    if not relics:
        d.text((W // 2, H // 2), "The first relic awaits.", font=_font(56), fill=GOLD, anchor="mm")
        return im
    y = 470
    for r in relics[:6]:
        c = RARITY.get(r.get("rarity", "common"), CREAM)
        d.rounded_rectangle([110, y, W - 110, y + 180], radius=24, fill=(24, 19, 16), outline=c, width=4)
        d.ellipse([150, y + 45, 240, y + 135], fill=c)
        d.text((280, y + 62), r["name"], font=_font(50, bold=True), fill=CREAM, anchor="lm")
        d.text((280, y + 125), f"{r.get('rarity', '').upper()} · {ERA_LABELS.get(r['era'], r['era'])}",
               font=_font(30, serif=False), fill=c, anchor="lm")
        y += 215
    if len(relics) > 6:
        d.text((W // 2, y + 40), f"+{len(relics) - 6} more", font=_font(40), fill=GOLD, anchor="mm")
    return im


def _scene_close(drachmae: int, line: str) -> Image.Image:
    im = _bg()
    d = ImageDraw.Draw(im)
    d.text((W // 2, 640), f"{drachmae:,}", font=_font(170, bold=True), fill=GOLD, anchor="mm")
    d.text((W // 2, 790), "DRACHMAE", font=_font(56, serif=False, bold=True), fill=CREAM, anchor="mm")
    f = _font(52)
    y = 1000
    for ln in _wrap(d, f"“{line}”", f, W - 220)[:4]:
        d.text((W // 2, y), ln, font=f, fill=CREAM, anchor="mm")
        y += 72
    d.text((W // 2, 1500), "Find your way home.", font=_font(46, bold=True), fill=RED, anchor="mm")
    return im


class _Line(BaseModel):
    narration: str
    closing_line: str


async def _narration(handle: str, path: str, entry: Optional[str], relics: list[dict], drachmae: int) -> _Line:
    era = ERA_LABELS.get(entry or "today", "Today")
    names = ", ".join(r["name"] for r in relics[:4]) or "none yet"
    res = await gemini.generate_json(
        f"Write a 12-second spoken recap (max 32 words) for a fan's shareable 'My FaZe Odyssey' video, as the Bard of Ithaca. "
        f"handle={handle}; path={path}; entry era={era}; relics={names}; drachmae={drachmae}. "
        f"Also a closing_line under 10 words. No hashtags, no emojis.", _Line, timeout=8, temperature=0.8)
    if res:
        return res
    if path == "odysseus":
        n = f"Sing, Muse, of {handle}, who sailed with FaZe in the {era} days, wandered far, and came home. Relics claimed. The voyage continues."
        c = "Odysseus came home. So can you."
    else:
        n = f"Sing, Muse, of {handle}, who came seeking the legend of FaZe, and found it. The voyage has only begun."
        c = "The son found the father's story."
    return _Line(narration=n, closing_line=c)


async def _ffmpeg(args: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec("ffmpeg", "-y", "-loglevel", "error", *args,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, err = await asyncio.wait_for(proc.communicate(), timeout=90)
    if proc.returncode != 0:
        raise RuntimeError(err.decode()[-800:])


async def render(fan: dict, relics: list[dict]) -> dict:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not installed")
    s = get_settings()
    out_dir = s.audio_dir.parent / "recaps"
    out_dir.mkdir(parents=True, exist_ok=True)
    handle = fan.get("handle") or fan["id"]
    path = fan.get("path") or "telemachus"
    state = f"{fan['id']}|{handle}|{path}|{fan.get('entry_era')}|{fan.get('drachmae', 0)}|{sorted(r['id'] for r in relics)}"
    key = hashlib.sha1(state.encode()).hexdigest()[:14]
    mp4 = out_dir / f"{key}.mp4"
    url = f"{s.public_base_url.rstrip('/')}/static/recaps/{key}.mp4"
    if mp4.exists() and mp4.stat().st_size > 0:
        return {"video_url": url, "cached": True, "key": key}

    line = await _narration(handle, path, fan.get("entry_era"), relics, fan.get("drachmae", 0))
    collected: dict[str, int] = {}
    for r in relics:
        collected[r["era"]] = collected.get(r["era"], 0) + 1
    work = out_dir / f"_{key}"
    work.mkdir(exist_ok=True)
    scenes = [_scene_title(handle, path), _scene_map(fan.get("entry_era"), collected),
              _scene_relics(relics), _scene_close(fan.get("drachmae", 0), line.closing_line)]
    pngs = []
    for i, im in enumerate(scenes):
        p = work / f"s{i}.png"
        im.save(p)
        pngs.append(p)

    audio_url = await tts.narrate(line.narration)
    audio_path = s.audio_dir / audio_url.rsplit("/", 1)[-1] if audio_url else None

    seg = (DUR + FADE * (SCENES - 1)) / SCENES  # each scene's length so total = DUR after crossfades
    args: list[str] = []
    for p in pngs:
        args += ["-i", str(p)]  # single frame; zoompan expands it to seg seconds
    if audio_path and audio_path.exists():
        args += ["-i", str(audio_path)]
    else:
        args += ["-f", "lavfi", "-t", f"{DUR}", "-i", "anullsrc=r=44100:cl=stereo"]
    # slow push-in on every scene, then crossfade chain
    f = [f"[{i}:v]scale={W}:{H},zoompan=z='min(zoom+0.0003,1.03)':d={int(seg * 30)}:s={W}x{H}:fps=30,format=yuv420p[v{i}]"
         for i in range(SCENES)]
    prev, off = "v0", seg - FADE
    for i in range(1, SCENES):
        f.append(f"[{prev}][v{i}]xfade=transition=fade:duration={FADE}:offset={off:.3f}[x{i}]")
        prev, off = f"x{i}", off + seg - FADE
    f.append(f"[{SCENES}:a]apad,atrim=0:{DUR},afade=t=out:st={DUR - 1}:d=1[a]")
    args += ["-filter_complex", ";".join(f), "-map", f"[{prev}]", "-map", "[a]", "-t", f"{DUR}",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(mp4)]
    try:
        await _ffmpeg(args)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return {"video_url": url, "cached": False, "key": key, "narration": line.narration, "has_voice": bool(audio_url)}

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR, get_settings
from app.routes import router
from app.services import bard
from app.services.lore import lore
from app.services.store import init_store, store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    s.audio_dir.mkdir(parents=True, exist_ok=True)
    await lore().init()
    await init_store()
    bard.load_cache()
    yield


app = FastAPI(title="ITHACA API", version="0.1.0", lifespan=lifespan,
              description="Every fan's road home to FaZe. Bard, Oracle, Siren, War Room.")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in get_settings().cors_origins.split(",")],
                   allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(router)


@app.get("/health", tags=["ops"])
async def health():
    s = get_settings()
    return {
        "ok": True,
        "gemini": s.has_gemini, "gemini_model": s.gemini_model,
        "elevenlabs": s.has_elevenlabs,
        "bard_agent": s.has_bard_agent,
        "chert_imessage": s.has_chert,
        "chert_webhook_signed": bool(s.chert_webhook_secret),
        "lore_backend": lore().backend, "lore_entries": len(lore().entries),
        "store_backend": store().kind,
        "youtube_ingest": bool(s.youtube_api_key),
        "service_key_enforced": bool(s.ithaca_api_key),
        "fan_token_enforced": s.require_fan_token,
    }


@app.get("/oracle/cam", include_in_schema=False)
async def oracle_cam():
    """FaceTime fallback: same Oracle, laptop camera."""
    return FileResponse(BASE_DIR / "static" / "oracle_cam.html")


@app.get("/bard", include_in_schema=False)
async def bard_page():
    """Part B: talk to the Bard (ElevenLabs agent) -> classified -> Odyssey Map. Text fallback if no agent."""
    return FileResponse(BASE_DIR / "static" / "bard.html")


@app.get("/test", include_in_schema=False)
async def test_page():
    """Plain page that exercises every endpoint (dev only)."""
    return FileResponse(BASE_DIR / "static" / "test.html")

"""Settings. Every external service is optional: missing key -> local fallback.
That way the demo never dies because one sponsor key is missing or slow."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # Gemini (AI Studio)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"          # bump to newest Flash at the event
    gemini_embed_model: str = "gemini-embedding-001"
    embed_dim: int = 768

    # ElevenLabs
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"  # replace with the Bard voice
    elevenlabs_model: str = "eleven_multilingual_v2"

    # MongoDB Atlas (lore)
    mongodb_uri: str = ""
    mongodb_db: str = "ithaca"
    atlas_vector_index: str = "lore_vector"

    # Tiger Data (Postgres + Timescale)
    tiger_dsn: str = ""

    # Behaviour
    public_base_url: str = "http://localhost:8000"   # set to https://api.<domain> on Vultr
    oracle_timeout_s: float = 6.0
    bard_timeout_s: float = 20.0
    cors_origins: str = "*"
    lore_seed_path: Path = BASE_DIR / "data" / "lore_seed.json"
    audio_dir: Path = BASE_DIR / "static" / "audio"

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def has_elevenlabs(self) -> bool:
        return bool(self.elevenlabs_api_key)

    @property
    def has_mongo(self) -> bool:
        return bool(self.mongodb_uri)

    @property
    def has_tiger(self) -> bool:
        return bool(self.tiger_dsn)


@lru_cache
def get_settings() -> Settings:
    return Settings()

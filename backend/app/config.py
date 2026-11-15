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
    gemini_model: str = "gemini-3.5-flash"
    gemini_embed_model: str = "gemini-embedding-001"
    embed_dim: int = 768

    # ElevenLabs
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"  # replace with the Bard voice
    elevenlabs_model: str = "eleven_multilingual_v2"
    # Part B: the Bard onboarding agent (ElevenLabs Agents). Create it with `python -m scripts.setup_bard_agent`.
    elevenlabs_agent_id: str = ""
    elevenlabs_agent_llm: str = "gemini-2.5-flash"
    elevenlabs_agent_public: bool = False  # true = browser connects with agent_id; false = we mint signed URLs

    # Part B: Chert (iMessage send/receive; FaceTime runs through oracle_agent/ + `chert dev`)
    chert_api_key: str = ""                 # Bearer key from the Chert console (docs call it the signing secret)
    chert_base_url: str = "https://console.trychert.com/api/v1"
    chert_webhook_secret: str = ""          # subscription secret, verifies X-Webhook-Signature on inbound events
    chert_line: str = ""                    # the Oracle's phone number, shown in texts ("FaceTime +1...")
    chert_optin_path: Path = BASE_DIR / "data" / "imessage_optin.json"  # phones that texted OMEN (gitignored)

    # MongoDB Atlas (lore)
    mongodb_uri: str = ""
    mongodb_db: str = "ithaca"
    atlas_vector_index: str = "lore_vector"

    # Tiger Data (Postgres + Timescale)
    tiger_dsn: str = ""

    # YouTube Data API v3 (ingest worker)
    youtube_api_key: str = ""

    # Twitch (P1 live trials) — EventSub webhook secret is any 10-100 char string you choose
    twitch_client_id: str = ""
    twitch_client_secret: str = ""
    twitch_eventsub_secret: str = ""

    # Auth: ITHACA_API_KEY guards server-to-server routes (agent tools, Chert webhook, admin) when set.
    # Fans get an HMAC-signed token from onboarding; enforced on fan routes only if REQUIRE_FAN_TOKEN=true.
    ithaca_api_key: str = ""
    token_secret: str = "dev-secret-change-me"
    require_fan_token: bool = False

    # Behaviour
    hub_base_url: str = "http://localhost:3000"      # C's Next.js hub, for iMessage links
    public_base_url: str = "http://127.0.0.1:8080"   # set to https://api.<domain> on Vultr
    # Fallback chain (comma-separated, in order). Gemini dates merch far better; the local Ollama model keeps the
    # demo alive when Gemini's quota runs out or the Wi-Fi drops. The canned line is always last.
    oracle_providers: str = "gemini,ollama"
    text_providers: str = "gemini,ollama"  # Bard scripts and answers
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_vision_model: str = "qwen2.5vl:3b"
    ollama_timeout_s: float = 20.0  # first call loads the model into memory, which takes several seconds
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
    def has_chert(self) -> bool:
        return bool(self.chert_api_key)

    @property
    def has_bard_agent(self) -> bool:
        return bool(self.elevenlabs_agent_id)

    @property
    def has_mongo(self) -> bool:
        return bool(self.mongodb_uri)

    @property
    def has_tiger(self) -> bool:
        return bool(self.tiger_dsn)


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""Light auth for a hackathon:
- Service key (X-Ithaca-Key) for server-to-server callers: ElevenLabs agent tools, Chert webhook, admin.
  Only enforced when ITHACA_API_KEY is set, so local dev just works.
- Fan token: HMAC(fan_id) returned at onboarding. Clients send `Authorization: Bearer <token>`.
  Only enforced on fan-scoped writes when REQUIRE_FAN_TOKEN=true."""
import hashlib
import hmac
import secrets
from typing import Optional

from fastapi import Header, HTTPException

from app.config import get_settings


def fan_token(fan_id: str) -> str:
    sig = hmac.new(get_settings().token_secret.encode(), fan_id.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{fan_id}.{sig}"


def verify_fan_token(token: str) -> Optional[str]:
    fan_id, _, sig = token.rpartition(".")
    if fan_id and secrets.compare_digest(fan_token(fan_id), token):
        return fan_id
    return None


async def require_service_key(x_ithaca_key: Optional[str] = Header(default=None)) -> None:
    key = get_settings().ithaca_api_key
    if key and not (x_ithaca_key and secrets.compare_digest(x_ithaca_key, key)):
        raise HTTPException(401, "missing or bad X-Ithaca-Key")


def check_fan(fan_id: Optional[str], authorization: Optional[str]) -> None:
    """Call inside fan-scoped write routes."""
    s = get_settings()
    if not s.require_fan_token or not fan_id:
        return
    tok = (authorization or "").removeprefix("Bearer ").strip()
    if verify_fan_token(tok) != fan_id:
        raise HTTPException(401, "fan token required (Authorization: Bearer <fan_token>)")

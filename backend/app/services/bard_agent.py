"""Part B: the Bard onboarding agent on ElevenLabs Agents (Conversational AI).

The agent lives at ElevenLabs. It holds the 60-second interview and calls our API as webhook tools:
  classify_fan -> POST {PUBLIC_BASE_URL}/tools/classify_fan   (Odysseus or Telemachus + entry era)
  get_lore     -> POST {PUBLIC_BASE_URL}/tools/get_lore       (grounded answers)
and one client tool the browser implements:
  show_odyssey_map {fan_id, path, entry_era} -> the Hub draws the map while the Bard is still talking.

The browser never sees our ELEVENLABS_API_KEY: it asks POST /bard/agent/session for a signed URL plus a
pre-created fan_id, which it passes to the agent as the `fan_id` dynamic variable. The agent sends that
fan_id back in classify_fan, so the Hub already knows whose map to draw.

`python -m scripts.setup_bard_agent` creates/updates the agent from `agent_config()`.
"""
import logging
from typing import Optional

import httpx

from app.config import get_settings

log = logging.getLogger("ithaca.bard_agent")
API = "https://api.elevenlabs.io/v1"

FIRST_MESSAGE = ("Sing to me, traveler. I am the Bard of Ithaca, keeper of the FaZe songs. "
                 "Tell me: when did you first find FaZe?")

SYSTEM_PROMPT = """You are the Bard of Ithaca (Demodocus): a warm, playful Homeric storyteller who keeps the history of FaZe Clan.
This is a short VOICE onboarding (about 60 seconds). Speak in short, natural sentences. No lists, no emojis, no markdown.

Your goal: learn three things, one question at a time, reacting briefly and warmly to each answer:
1. When they first found FaZe (a year, or "just recently").
2. Who was "their guy" (favorite FaZe member), if any.
3. What games they play now.
If they volunteer something early, don't ask again. Never ask more than one question per turn.

As soon as you know the year (or that they're new) and have heard about games, call the `classify_fan` tool.
(fan_id is filled in automatically.) If the fan's name is "{{handle}}" and not empty, pass it as handle.
Pass first_found_year as a number if they gave one, favorite_member, games, and a one-sentence transcript summary.

After classify_fan returns:
- Call `show_odyssey_map` with the fan_id, path and entry_era it returned.
- Then say the returned bard_line (you may lightly rephrase it) and one or two sentences of welcome:
  path "odysseus" = a returning fan: "you were there", welcome them home, name their era.
  path "telemachus" = a new fan: "here is the legend you missed".
- Then invite them to hear their first episode on the map, and say farewell.

If they ask about FaZe history, call `get_lore` and answer ONLY from what it returns, in two or three sentences.
If the lore doesn't cover it, say the songs don't tell of that yet. Never invent dates, names, numbers or quotes.
Never claim to be an AI model or mention tools, APIs or JSON. Never ask for passwords, emails or payment details."""


def _prop(type_: str, desc: str, **extra) -> dict:
    return {"type": type_, "description": desc, **extra}


def webhook_tools(base_url: str, service_key: str = "") -> list[dict]:
    base = base_url.rstrip("/")
    headers = {"X-Ithaca-Key": service_key} if service_key else {}
    return [
        {
            "type": "webhook",
            "name": "classify_fan",
            "description": "Classify the fan as returning (odysseus) or new (telemachus) with their FaZe entry era. "
                           "Call once, after learning when they found FaZe and what they play.",
            "api_schema": {
                "url": f"{base}/tools/classify_fan",
                "method": "POST",
                "request_headers": headers,
                "request_body_schema": {
                    "type": "object",
                    "description": "What the fan told the Bard.",
                    "properties": {
                        # filled by ElevenLabs from the session's dynamic variable, not by the LLM
                        # (ElevenLabs wants exactly one of description / dynamic_variable / constant_value)
                        "fan_id": {"type": "string", "description": "", "dynamic_variable": "fan_id"},
                        "handle": _prop("string", "The fan's name or gamer tag if they said it."),
                        "first_found_year": _prop("integer", "Year they first found FaZe, e.g. 2012. Omit if unknown."),
                        "favorite_member": _prop("string", "Their favorite FaZe member, e.g. Rug, Clip, Swagg."),
                        "games": {"type": "array", "description": "Games they play now.",
                                  "items": {"type": "string", "description": "A game title"}},
                        "transcript": _prop("string", "One or two sentences summarizing what the fan said."),
                    },
                    "required": ["fan_id"],
                },
            },
        },
        {
            "type": "webhook",
            "name": "get_lore",
            "description": "Look up FaZe history to answer a question. Answer only from what this returns.",
            "api_schema": {
                "url": f"{base}/tools/get_lore",
                "method": "POST",
                "request_headers": headers,
                "request_body_schema": {
                    "type": "object",
                    "description": "The lore search.",
                    "properties": {
                        "query": _prop("string", "What the fan asked about, e.g. 'the 1M celebration montage'."),
                        "era": _prop("string", "Optional era: 2010_trickshots, 2013_rug_era, 2020_nuke_squad, "
                                               "2022_snoop or today."),
                    },
                    "required": ["query"],
                },
            },
        },
    ]


def client_tools() -> list[dict]:
    return [{
        "type": "client",
        "name": "show_odyssey_map",
        "description": "Show the fan their Odyssey Map on screen. Call right after classify_fan returns.",
        "expects_response": False,
        "parameters": {
            "type": "object",
            "description": "Result of classify_fan.",
            "properties": {
                "fan_id": _prop("string", "fan_id returned by classify_fan"),
                "path": _prop("string", "odysseus or telemachus"),
                "entry_era": _prop("string", "entry_era returned by classify_fan"),
            },
            "required": ["fan_id"],
        },
    }]


def agent_config(*, tool_ids: Optional[list[str]] = None, inline_tools: Optional[list[dict]] = None) -> dict:
    s = get_settings()
    prompt: dict = {"prompt": SYSTEM_PROMPT, "llm": s.elevenlabs_agent_llm, "temperature": 0.6}
    if tool_ids is not None:
        prompt["tool_ids"] = tool_ids
    if inline_tools is not None:
        prompt["tools"] = inline_tools
    return {
        "name": "ITHACA - The Bard",
        "conversation_config": {
            "agent": {
                "first_message": FIRST_MESSAGE,
                "language": "en",
                "prompt": prompt,
                "dynamic_variables": {"dynamic_variable_placeholders": {"fan_id": "demo_odysseus", "handle": ""}},
            },
            "tts": {"voice_id": s.elevenlabs_voice_id},
            # Spelled out so a PATCH can't leave the agent deaf: high-quality speech recognition, a normal turn
            # timeout, and the client events the Hub needs (user_transcript is what shows the fan's own words).
            "asr": {"quality": "high"},
            "turn": {"turn_timeout": 7},
            "conversation": {
                "max_duration_seconds": 300,
                "client_events": ["audio", "interruption", "user_transcript", "agent_response",
                                  "agent_response_correction", "client_tool_call", "vad_score", "ping"],
            },
        },
        "platform_settings": {"auth": {"enable_auth": not s.elevenlabs_agent_public}},
    }


async def conversation_token() -> Optional[str]:
    """Short-lived WebRTC token for a private agent. WebRTC gives the browser echo cancellation and noise
    suppression, which is what lets the agent actually hear the fan on laptop mics. None if unavailable."""
    s = get_settings()
    if not (s.has_elevenlabs and s.has_bard_agent):
        return None
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(f"{API}/convai/conversation/token", params={"agent_id": s.elevenlabs_agent_id},
                            headers={"xi-api-key": s.elevenlabs_api_key})
        r.raise_for_status()
        return r.json().get("token")
    except Exception as e:
        log.warning("conversation token failed: %r", e)
        return None


async def signed_url() -> Optional[str]:
    """Short-lived wss URL for a private agent. None if not configured or the call fails."""
    s = get_settings()
    if not (s.has_elevenlabs and s.has_bard_agent):
        return None
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(f"{API}/convai/conversation/get-signed-url", params={"agent_id": s.elevenlabs_agent_id},
                            headers={"xi-api-key": s.elevenlabs_api_key})
        r.raise_for_status()
        return r.json().get("signed_url")
    except Exception as e:
        log.warning("signed url failed: %r", e)
        return None

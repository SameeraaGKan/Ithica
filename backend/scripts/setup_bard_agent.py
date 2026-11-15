"""Create or update the Bard onboarding agent on ElevenLabs (Part B).

    python -m scripts.setup_bard_agent            # create (prints ELEVENLABS_AGENT_ID to put in .env)
    python -m scripts.setup_bard_agent --print    # just print the JSON config (paste into the dashboard by hand)

Needs ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID (the Bard voice) and PUBLIC_BASE_URL (the tools must be reachable
from ElevenLabs' servers, so a public https URL: the Vultr box or a tunnel). If ITHACA_API_KEY is set, the tools
send it as X-Ithaca-Key. With ELEVENLABS_AGENT_ID already set, the agent is updated in place.

Tools are created as standalone workspace tools (POST /convai/tools) and attached by id; if that endpoint
isn't available on the account, they are sent inline in the agent prompt instead.
"""
import argparse
import asyncio
import json
import sys

import httpx

from app.config import get_settings
from app.services.bard_agent import API, agent_config, client_tools, webhook_tools


async def _tools(c: httpx.AsyncClient, tools: list[dict]) -> list[str] | None:
    ids = []
    for t in tools:
        r = await c.post(f"{API}/convai/tools", json={"tool_config": t})
        if r.status_code in (404, 405):
            return None
        if r.status_code >= 400:
            print(f"  tool {t['name']} rejected ({r.status_code}): {r.text[:400]}", file=sys.stderr)
            return None
        ids.append(r.json()["id"])
        print(f"  tool {t['name']}: {ids[-1]}")
    return ids


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true", help="print config JSON only")
    args = ap.parse_args()
    s = get_settings()
    tools = webhook_tools(s.public_base_url, s.ithaca_api_key) + client_tools()

    if args.print:
        print(json.dumps(agent_config(inline_tools=tools), indent=2))
        return
    if not s.has_elevenlabs:
        sys.exit("ELEVENLABS_API_KEY is not set")
    if "localhost" in s.public_base_url or "127.0.0.1" in s.public_base_url:
        print("WARNING: PUBLIC_BASE_URL is local; ElevenLabs can't reach the tools until it's a public https URL.",
              file=sys.stderr)

    async with httpx.AsyncClient(timeout=30, headers={"xi-api-key": s.elevenlabs_api_key}) as c:
        ids = await _tools(c, tools)
        cfg = agent_config(tool_ids=ids) if ids is not None else agent_config(inline_tools=tools)
        if s.elevenlabs_agent_id:
            r = await c.patch(f"{API}/convai/agents/{s.elevenlabs_agent_id}", json=cfg)
            verb, agent_id = "updated", s.elevenlabs_agent_id
        else:
            r = await c.post(f"{API}/convai/agents/create", json=cfg)
            verb, agent_id = "created", None
        if r.status_code >= 400:
            sys.exit(f"ElevenLabs said {r.status_code}: {r.text[:1000]}")
        agent_id = agent_id or r.json()["agent_id"]
    print(f"Bard agent {verb}: {agent_id}")
    if verb == "created":
        print(f"\nAdd to backend/.env:\nELEVENLABS_AGENT_ID={agent_id}")


if __name__ == "__main__":
    asyncio.run(main())

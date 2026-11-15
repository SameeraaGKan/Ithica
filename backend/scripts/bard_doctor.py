"""Why can't the Bard hear me? Run from backend/:  python -m scripts.bard_doctor

Reads the agent's live config and the last few voice calls from ElevenLabs, and prints what each call
actually received: did your speech get transcribed, did the LLM fail, did a tool time out, why it ended.
"""
from __future__ import annotations

import asyncio
import json
import sys

import httpx

from app.config import get_settings

API = "https://api.elevenlabs.io/v1"


def _pick(d: dict, *path, default=None):
    for p in path:
        if not isinstance(d, dict):
            return default
        d = d.get(p)
    return d if d is not None else default


async def main() -> None:
    s = get_settings()
    if not (s.elevenlabs_api_key and s.elevenlabs_agent_id):
        sys.exit("Set ELEVENLABS_API_KEY and ELEVENLABS_AGENT_ID in backend/.env first.")
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    async with httpx.AsyncClient(timeout=20, headers={"xi-api-key": s.elevenlabs_api_key}) as c:
        r = await c.get(f"{API}/convai/agents/{s.elevenlabs_agent_id}")
        if r.status_code >= 400:
            sys.exit(f"Couldn't read the agent ({r.status_code}): {r.text[:300]}\n"
                     "-> The key needs ElevenLabs Agents read/write access, and the agent id must be on this account.")
        cc = r.json().get("conversation_config", {})
        print("== Agent")
        print("  LLM:          ", _pick(cc, "agent", "prompt", "llm"))
        print("  ASR quality:  ", _pick(cc, "asr", "quality"), "| input format:", _pick(cc, "asr", "user_input_audio_format"))
        print("  turn timeout: ", _pick(cc, "turn", "turn_timeout"))
        ev = _pick(cc, "conversation", "client_events", default=[])
        print("  client events:", ", ".join(ev) or "(none)")
        if "user_transcript" not in ev:
            print("  !! user_transcript is missing: the Hub never sees your words. Run: python -m scripts.setup_bard_agent")
        for t in _pick(cc, "agent", "prompt", "tools", default=[]) or []:
            url = _pick(t, "api_schema", "url")
            if url:
                bad = "localhost" in url or "127.0.0.1" in url
                print(f"  tool {t.get('name')}: {url}{'   !! local URL, ElevenLabs cannot reach it' if bad else ''}")

        r = await c.get(f"{API}/convai/conversations", params={"agent_id": s.elevenlabs_agent_id, "page_size": n})
        convs = r.json().get("conversations", []) if r.status_code < 400 else []
        if not convs:
            print("\n== No calls recorded yet for this agent (or the key can't read history).")
            return
        for cv in convs:
            d = (await c.get(f"{API}/convai/conversations/{cv['conversation_id']}")).json()
            meta = d.get("metadata", {}) or {}
            print(f"\n== Call {cv['conversation_id']}  status={d.get('status')}  "
                  f"{meta.get('call_duration_secs', '?')}s")
            for k in ("termination_reason", "error", "feedback"):
                if meta.get(k):
                    print(f"  {k}: {meta[k] if isinstance(meta[k], str) else json.dumps(meta[k])[:300]}")
            user_turns = 0
            for m in d.get("transcript", []) or []:
                role, msg = m.get("role"), (m.get("message") or "").strip()
                user_turns += role == "user"
                tools = [tc.get("tool_name") for tc in (m.get("tool_calls") or [])]
                res = [f"{tr.get('tool_name')}={'ERROR' if tr.get('is_error') else 'ok'}"
                       for tr in (m.get("tool_results") or [])]
                extra = f"  [tools: {', '.join(tools)}]" if tools else ""
                extra += f"  [results: {', '.join(res)}]" if res else ""
                print(f"  {role:>5}: {msg[:140] or '(no text)'}{extra}")
            if user_turns == 0:
                print("  !! ElevenLabs heard nothing from you on this call: the mic audio never arrived or was silent.")
                print("     Check Chrome's mic choice (lock icon -> Site settings) and Windows Sound -> Input level.")


if __name__ == "__main__":
    asyncio.run(main())

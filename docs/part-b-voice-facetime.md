# Part B: Voice + FaceTime (the Bard agent, the Oracle on FaceTime, iMessage)

Role B from the plan: **ElevenLabs agent + tools, Chert FaceTime/iMessage integration.**

| Piece | Where | What it does |
|---|---|---|
| Bard onboarding agent | `backend/app/services/bard_agent.py`, `backend/scripts/setup_bard_agent.py` | ElevenLabs Agent: 60s interview → `classify_fan` tool → `show_odyssey_map` client tool → Bard line |
| Voice session for the Hub | `POST /bard/agent/session` | Pre-creates the fan, returns `signed_url` (or `agent_id`) + `dynamic_variables` |
| Arrival page | `GET /bard` (`backend/static/bard.html`) | Talk to the Bard → map appears → play first episode. Has a written fallback if voice is down |
| Oracle on FaceTime | `oracle_agent/agent.py` | LiveKit worker that `chert dev` bridges calls into. Watches the caller camera, speaks verdicts in the ElevenLabs voice |
| FaceTime API | `POST /chert/facetime/start`, `POST /chert/facetime/verdict` | Caller → fan, frame → Oracle verdict, iMessage relic card queued |
| iMessage | `backend/app/services/chert.py`, `POST /chert/webhook` | Signed inbound webhook; replies with menu / Daily Omen / map link / Bow Trial / Ask the Bard |
| Daily Omen | `POST /omen/broadcast` | Texts today's omen to everyone who texted OMEN (cron it) |

Everything runs with **no keys**: no agent → `/bard` shows the written path; no Chert key → iMessages are a dry run you can read at `GET /chert/outbox`.

## 1. The Bard (ElevenLabs Agents)

```bash
cd backend
# .env: ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID (the Bard voice), PUBLIC_BASE_URL=https://api.<domain>, ITHACA_API_KEY (optional)
python -m scripts.setup_bard_agent          # prints ELEVENLABS_AGENT_ID=... -> add to .env, restart API
python -m scripts.setup_bard_agent --print  # or paste the JSON into the ElevenLabs dashboard by hand
```

Re-run it any time to push prompt/tool changes (it updates the agent when `ELEVENLABS_AGENT_ID` is set).
The tools must be reachable from ElevenLabs, so `PUBLIC_BASE_URL` has to be the public Vultr URL (or a tunnel).

**For C (Hub)**, with `@elevenlabs/react` or `@elevenlabs/client`:

```js
const s = await fetch(`${API}/bard/agent/session`, {method: "POST", headers: {"Content-Type": "application/json"},
                                                    body: JSON.stringify({handle})}).then(r => r.json());
// s.mode: "signed" | "public" | "unconfigured" (show a written form and POST /onboard/classify instead)
await Conversation.startSession({
  signedUrl: s.signed_url,                // or agentId: s.agent_id when mode === "public"
  dynamicVariables: s.dynamic_variables,  // {fan_id, handle}: the agent passes fan_id back in classify_fan
  clientTools: { show_odyssey_map: async ({fan_id}) => router.push(`/odyssey/${fan_id}`) },
});
// keep s.fan_token for Authorization: Bearer on fan writes
```

`/bard` is a working reference implementation of exactly this.

## 2. The Oracle on FaceTime (Chert + LiveKit)

Chert's FaceTime product bridges a call into a LiveKit room; your agent joins by name.
The caller's camera arrives as the `facetime-remote-video` track (caller capture must be enabled on the line).

```bash
cd oracle_agent
python -m venv .venv && .venv\Scripts\activate      # mac/linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env.local                         # LiveKit project creds, ElevenLabs key + voice, ITHACA_API_URL/KEY
python agent.py dev                                # terminal 1
chert dev --agent ithaca-oracle                    # terminal 2 (after `chert` sign-in, see Chert's "Connect and test")
```

Then FaceTime **video** the assigned line. Flow: greeting → *hold up your FaZe relic* (Argos, up to 3 looks) →
*play your trickshot* (Bow Trial) → rank → "your relic card sails to you by iMessage".

**Confirm at the Chert table:**
- Where the caller's phone number shows up in the room. `find_phone()` searches participant attributes/metadata,
  room metadata and job metadata and logs every key it saw (`caller info keys: ...`). Pin the right key once known.
  Without a number the call still works; relics go to an `ft_<room>` fan and no iMessage is sent.
- That caller capture (video) is enabled for our line. FaceTime Audio calls get a polite "call me on video".

**Fallback** if Chert has a hiccup on stage: the same Oracle runs at `GET /oracle/cam` (laptop camera).

## 3. iMessage (Chert Messaging API)

```bash
# .env: CHERT_API_KEY (console key), CHERT_LINE=+1..., PUBLIC_BASE_URL public
python -m scripts.chert_subscribe        # subscribes {PUBLIC_BASE_URL}/chert/webhook to message.received
# put the returned secret in CHERT_WEBHOOK_SECRET -> signature verification on
```

Texting the line:

| Text | Reply |
|---|---|
| hi / help / anything first | welcome + menu |
| `OMEN` | opts in, sends today's omen; the next text is graded (+50 Drachmae) |
| `MAP` | relics, Drachmae, Odyssey link |
| `TRIAL` | this week's (sponsored) Bow Trial + "FaceTime the Oracle" |
| a photo | "FaceTime me and hold it up" |
| `STOP` | leaves the Omen list |
| any question | Ask the Bard (grounded in lore) |

Daily Omen cron on the Vultr box: `0 16 * * * curl -s -X POST -H "X-Ithaca-Key: $KEY" https://api.<domain>/omen/broadcast`

**Privacy:** phones are stored hashed. The only raw numbers kept are fans who texted OMEN
(`backend/data/imessage_optin.json`, gitignored), because we must have the number to text them; STOP deletes it.
FaceTime frames are processed in memory and discarded.

## Not verified yet

Written against Chert's and ElevenLabs' public docs but not run against live keys (none were available while building):
the ElevenLabs agent/tool JSON schema, Chert's webhook-subscription response fields, the exact LiveKit Agents
version API (`livekit-agents` pinned to 1.2.x), and how Chert exposes the caller's number. Check those first at the tables.

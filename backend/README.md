# ITHACA backend (Part A)

FastAPI service for the Bard (RAG → Gemini → ElevenLabs), the Oracle (Gemini vision verdicts), the Siren, the War Room and the ElevenLabs agent tools.

**It runs with no keys.** Each missing or slow service falls back: keyword lore search instead of vectors, template episodes instead of Gemini, canned Oracle lines after 6s, in-memory store with simulated War Room history. `GET /health` shows what's live.

## Run

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # fill whatever keys you have
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs for the interactive API, or http://localhost:8000/oracle/cam for the camera fallback Oracle.

## Turning sponsors on

| Service | Env | Then |
|---|---|---|
| Gemini | `GEMINI_API_KEY` (`GEMINI_MODEL` = newest Flash) | episodes, Oracle, transcript classify, embeddings go live |
| ElevenLabs | `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` (the Bard voice) | episodes get `audio_url` (cached mp3 in `static/audio/`) |
| MongoDB Atlas | `MONGODB_URI` | `python -m scripts.load_lore`, then create index from `scripts/atlas_vector_index.json` |
| Tiger Data | `TIGER_DSN` | `psql "$TIGER_DSN" -f sql/schema.sql`, then `python -m scripts.seed_tiger` |
| Vultr | `PUBLIC_BASE_URL=https://api.<domain>` | so audio URLs resolve publicly |

Before the demo: `python -m scripts.pregen_episodes` caches every era × path episode with audio.

## API (contracts in `app/schemas.py`)

| Method | Path | Who calls it | Notes |
|---|---|---|---|
| POST | `/onboard/classify` | Bard agent / Hub | `{handle?, phone?, first_found_year?, favorite_member?, games[], transcript?}` → `fan_id, path, entry_era, bard_line` |
| POST | `/tools/classify_fan` | **B** ElevenLabs agent tool | alias of the above |
| POST | `/tools/get_lore` | **B** agent tool ("Ask the Bard") | `{query, era?}` → `{answer, lore_ids}` |
| GET | `/odyssey/{fan_id}` | **C** Hub | map nodes, relics, Drachmae, next episode |
| POST | `/bard/episode` | **C** Hub | `{fan_id? , era?, path?, topic?, voice}` → script, `audio_url`, `cues[]` (YouTube id + start/end) |
| POST | `/oracle/frame` | **B** Chert / cam page | multipart `image`+`mode`+`fan_id` **or** JSON `{image_b64, mode, fan_id, source}`; `mode` = `argos` \| `bow_trial` → `spoken`, era/score, relic, Drachmae |
| POST | `/chert/webhook` | **B** | placeholder: adapt to Chert's real payload; returns `{say}` |
| GET | `/siren/context?videoId=&t=&channel=` | **D** extension | lore at this moment + relic available |
| POST | `/siren/collect` | **D** extension | `{fan_id, video_id, t, lore_id}` (pass `lore_id` from context) |
| POST | `/bard/ask` | **D** extension push-to-talk / Hub | `{question, video_id?, t?, fan_id?}` → grounded answer + `audio_url` |
| GET | `/trials/current` | **C** Hub | this week's Bow Trial: prompt, sponsor, pass score |
| GET | `/trials/leaderboard` | **C** Hub | the Suitors: best score per fan (simulated suitors flagged) |
| POST | `/trials/current?sponsor=&prompt=` | admin (service key) | set the sponsored trial; logs the sponsorship revenue |
| GET | `/omen/today` | **B** (P1) | daily quest + ready-to-send `imessage_text` |
| POST | `/omen/answer` | **B** (P1) | `{fan_id, answer}` → `{correct, reply, drachmae_awarded}` |
| POST | `/recap/{fan_id}` | **C** Hub share button | renders/caches a vertical 15s "My FaZe Odyssey" mp4 → `video_url` |
| POST | `/twitch/eventsub` | Twitch | signed EventSub webhook: `!bow` in chat or a "Bow Trial" channel-points reward queues a challenger |
| GET | `/twitch/live` | overlay | queue, current challenger, recent verdicts |
| POST | `/twitch/live/next` · `/twitch/live/judge` · `/twitch/live/queue` | streamer control (service key) | pull next, judge frame, manual queue |
| GET | `/warroom/metrics?days=14` | **C** War Room | totals, revenue by stream, era-drop demand, daily series; `simulated` flag |
| POST | `/pass/checkout?fan_id=&sku=` | **C** | mocked Odyssey Pass / Era Drop purchase |

Oracle verdicts include `imessage_text` + `share_url`. **B** sends those over Chert iMessage after the call. Bow Trial verdicts also carry `trial_id`, `sponsor`, `rank`.

Demo fan: `demo_odysseus` (returning fan, Rug era, two relics) is always seeded.

## Auth

- **Service key**: set `ITHACA_API_KEY` and server-to-server callers (ElevenLabs agent tools, Chert webhook, admin) must send `X-Ithaca-Key`. Unset = open (dev).
- **Fan token**: onboarding returns `fan_token`. Clients send `Authorization: Bearer <fan_token>`. Enforced on fan writes (Oracle, collect, checkout, omen) only with `REQUIRE_FAN_TOKEN=true`. Leave it off for the demo unless C wires it.

## Ingest (YouTube Data API)

```bash
python -m scripts.ingest_youtube            # top videos + video_id suggestions per lore entry
python -m scripts.ingest_youtube --write    # also save uploads into lore_seed.json video_index
python -m scripts.load_lore                 # push lore + video_index to Atlas
```
D's script (stdlib only). Channel via `FAZE_HANDLE` (default `@FaZeClan`).

## Recap, Twitch, transcripts (P1)

- **Recap**: needs `ffmpeg` on the box (`ops/vultr_setup.sh` installs it). Narration uses Gemini + ElevenLabs when keyed.
- **Twitch**: set `TWITCH_CLIENT_ID/SECRET/EVENTSUB_SECRET`, then `python -m scripts.twitch_subscribe --broadcaster <you> --bot-user <you>`. OBS browser source: `/twitch/overlay`. Streamer control (camera + buttons): `/twitch/overlay?control=1&key=<ITHACA_API_KEY>`. No stream handy? Queue challengers manually from the control page.
- **Transcripts**: `python -m scripts.ingest_transcript --video-id <id> --captions file.vtt` (or `--audio clip.mp3` → Whisper if `faster-whisper` is installed, else Gemini). Siren context then returns `transcript`, and Ask the Bard uses it as a source.

## Tests

```bash
pytest -q
```

Eras: `2010_trickshots`, `2013_rug_era`, `2020_nuke_squad`, `2022_snoop`, `today`. Paths: `odysseus`, `telemachus`.

## Lore

`data/lore_seed.json` is D's curated lore: 31 sourced entries with `verified` and `sensitive` flags. `video_id`s are still to fill (see Ingest). After edits run `ops/sync_lore.sh`. The Bard prompt is told to use only facts in the lore, so the lore is the accuracy ceiling.

## Deploy (Vultr)

D's scripts in `ops/` (see `docs/siren-data-ops.md`):

```bash
# once, on a fresh Ubuntu VM as root (DNS A record for api.<domain> first)
DOMAIN=api.yourdomain.com bash ops/vultr_setup.sh
nano /etc/ithaca.env && systemctl restart ithaca-api
# every redeploy
sudo bash /opt/ithaca/ops/redeploy.sh
```

Caddy does HTTPS, systemd keeps uvicorn alive (1 worker, because of the in-memory fallback store). `ops/sync_lore.sh` copies edited lore into the extension and reloads Atlas.

## Not built (P1/P2, by the plan's cut order)

Grok suitor commentator, Solana relics, Discord bot (P2, first in the cut order).

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
| GET | `/warroom/metrics?days=14` | **C** War Room | totals, revenue by stream, era-drop demand, daily series; `simulated` flag |
| POST | `/pass/checkout?fan_id=&sku=` | **C** | mocked Odyssey Pass / Era Drop purchase |

Eras: `2010_trickshots`, `2013_rug_era`, `2020_nuke_squad`, `2022_snoop`, `today`. Paths: `odysseus`, `telemachus`.

## Lore

`data/lore_seed.json` is a **starter seed** (12 entries, `verified: false`, no video IDs yet). D replaces it with the curated 25–30 entries from the FaZe timeline, then reruns `scripts.load_lore`. The Bard prompt is told to use only facts in the lore, so the lore is the accuracy ceiling.

## Deploy (Vultr)

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1   # behind Caddy: reverse_proxy localhost:8000
```

Keep `--workers 1` while using the in-memory store.

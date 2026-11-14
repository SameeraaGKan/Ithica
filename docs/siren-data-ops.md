# D: Siren extension, lore data, ops

```
backend/data/lore_seed.json      30 researched lore entries (+ A's "Your road home" closer), 5 eras, sources per entry
backend/scripts/ingest_youtube.py FaZe channel uploads → top-viewed list + video_id suggestions (--write fills video_index)
extension/                       The Siren (Chrome MV3 side panel), speaks backend/app/routes.py /siren/*
ops/vultr_setup.sh               fresh Ubuntu VM → Caddy HTTPS + systemd uvicorn (backend/, app.main:app)
ops/redeploy.sh                  pull + restart + health check
ops/sync_lore.sh                 after editing lore: copy into extension + reload Atlas
```

## 1. The Siren extension

1. `chrome://extensions` → turn on Developer mode → **Load unpacked** → pick `extension/`.
2. Run the backend (`cd backend && uvicorn app.main:app --port 8000`), open a FaZe video on YouTube and click the Siren icon.
3. The status line shows **Live · Ithaca API** (green). If the API is down or slower than 2.5s, it shows **Offline lore** and uses the bundled `extension/lore_seed.json`. Relics collected offline are queued and sent when the API returns.
4. After deploying, open the **⚙ settings** in the panel and set the API base to `https://api.<domain>`. No rebuild needed.

What it calls (A's contract, unchanged):
- `GET /siren/context?videoId=&t=&channel=`. The panel merges the bundled copy of the entry so "Jump to this moment" works once `video_id`/`start_s` are filled in.
- `POST /siren/collect {fan_id, video_id, t, lore_id}`. Drachmae shown are `drachmae_total` from the response.
- **Ask the Bard** opens `<Hub>/bard?fan_id=&lore=&videoId=&t=` (C/B: host the ElevenLabs agent there; MV3 can't load its widget script).
- CORS: the backend's `cors_origins="*"` default works. If you lock it down, allow `chrome-extension://<id>`.

## 2. Lore (`backend/data/lore_seed.json`)

- Era ids match `app/schemas.py` ERAS. Every entry has its own relic, so 31 relics in total. The Swagg entry keeps `r_swagg_bow` because the Bow Trial awards it.
- **Relic ids changed from the starter seed.** On Tiger, re-run `python -m scripts.seed_tiger` from `backend/` so the relic catalog gets upserted. Then run `python -m scripts.load_lore` for Atlas.
- `verified: false` (8 entries) means a detail is disputed or weakly sourced; `verify_note` says which. `sensitive: true` marks the IPO crash, Snoop leaving the board, and the 2026 creator exit. The extension's offline rotation skips these. Suggestion for A: skip them in `_lore_for`'s random pick too.
- `video_id` is still null everywhere. Run `YOUTUBE_API_KEY=... python -m scripts.ingest_youtube` and copy the right IDs and timestamps from its suggestions.

**For the pitch:**
- **The "12.1M views, most-watched video" hook is not verified.** `ingest_youtube` prints the channel's top 5. Check it there.
- **The Swagg story:** FaZe's press release says Swagg surprised his Nuke Squad friends live on stream with the news that they had joined FaZe (March 2020). Use that line instead of "Swagg got his offer live on stream".
- **FaZe today:** the creator division closed on Jan 1, 2026; FaZe is now esports-first. It launched the **FaZe Up Next** academy in April 2026, which is the natural target for the talent funnel.

## 3. Vultr + domain

1. Buy the domain with GoDaddy Registry code `MLHUTA76`. Add a DNS **A record** for `api` pointing at the VM's IP. Do this early: Chert's webhook needs `https://api.<domain>/chert/webhook`.
2. On a fresh Ubuntu 24.04 VM (after this branch is merged to `main`):
   ```bash
   curl -fsSL https://raw.githubusercontent.com/SameeraaGKan/Ithica/main/ops/vultr_setup.sh -o setup.sh
   DOMAIN=api.yourdomain.com bash setup.sh
   nano /etc/ithaca.env && systemctl restart ithaca-api     # keys from backend/.env.example
   ```
   Runs `uvicorn app.main:app` from `backend/` with **1 worker**, because the in-memory fallback store can't be shared across workers.
3. Redeploy: `sudo bash /opt/ithaca/ops/redeploy.sh`.

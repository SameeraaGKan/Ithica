# ITHACA web (Part C: Ithaca Hub + War Room)

Next.js 15 + Tailwind 4 + Framer Motion + Recharts. Every page works on seeded mock data
until the FastAPI backend is up, then switches to live data automatically.

## Run

```bash
npm install
cp .env.example .env.local   # fill in what you have
npm run dev                   # http://localhost:3000
```

## Pages

| Route | Feature (plan) |
|---|---|
| `/` | Landing: Talk to the Bard / Enter as demo fan |
| `/onboard` | Arrival: ElevenLabs Bard voice session (+ typed fallback) |
| `/odyssey/[fanId]` | Hub: Odyssey Map, Bard episode, relics, Drachmae (polls every 3s) |
| `/leaderboard` | The Suitors |
| `/pass` | Odyssey Pass upsell (mocked checkout) |
| `/oracle-cam` | FaceTime fallback: webcam → `POST /oracle/frame` → spoken verdict |
| `/warroom` | CTO/Board dashboard (polls `/warroom/metrics` every 5s) |
| `/health` | Endpoint health check |

## Contract with the backend (person A)

Types live in `lib/types.ts`. Endpoints used:

- `GET /odyssey/:fanId` → `Odyssey`
- `POST /onboard/classify` `{answers}` → `ClassifyResult`
- `POST /oracle/frame` `{fan_id, mode, image(base64 jpeg)}` → `OracleVerdict`
- `POST /siren/collect` `{fan_id, relic_id?, source}`
- `GET /warroom/metrics` → `WarroomMetrics` (include `simulated: true` while seeded)
- `GET /leaderboard` → `LeaderboardRow[]` (**not in the plan yet, ask A to add it**)

The backend needs CORS allowing the Hub's origin.

## Asks for teammates

- **B (voice):** give me the ElevenLabs Agent ID, and add a client tool `show_odyssey({fan_id})` to the agent so the Bard can route the fan to their map.
- **D (lore):** real FaZe `video_id` + `start_s`/`end_s` per episode; relic names/eras to match the lore JSON.
- **Demo audio:** put the pre-generated Bard episode at `public/audio/demo-episode.mp3`.

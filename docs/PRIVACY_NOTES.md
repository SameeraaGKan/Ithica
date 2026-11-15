# ITHACA privacy notes (for Devpost and Q&A)

Each claim below was checked against the code. Re-check if the code changes.

- **Oracle frames:** camera frames are sent to Gemini for judging and are not written to disk or the database. Only the verdict, era, score and any relic are stored.
- **Phone numbers:** stored only as a keyed hash (HMAC-SHA256 with the server's `TOKEN_SECRET`), never in plain text. Without the server secret the hash can't be reversed to a number.
- **Copyright:** FaZe's own YouTube videos are embedded at timestamps, not re-hosted. Bard narration is generated audio, and recap videos are rendered from our own graphics (map, relics, text), not from FaZe footage.
- **Fan identity:** each fan gets an HMAC-signed token. Fan-scoped writes are only checked when `REQUIRE_FAN_TOKEN=true`, which is off by default, so turn it on before the demo if you want to claim it.

Not covered yet (do not claim these in the pitch):
- **Moderation (partly built):** with Gemini on, every Bow Trial frame gets a safety check, and unsafe frames score 0 and never reach the leaderboard. With Gemini down, the fallback verdict skips that check, so it is shown to the fan but kept off the public leaderboard.
- **Deletion:** `DELETE /fan/{fan_id}/data` erases a fan's profile, relics, events, trial entries and purchases. Tested on the in-memory store; the Tiger Data path is written but not yet run against a database.
- **Retention:** no automatic retention period yet. Data stays until a deletion request.

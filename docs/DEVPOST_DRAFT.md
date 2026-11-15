# ITHACA — the road home to FaZe (Devpost draft)

**Inspiration.** FaZe's most-watched video is still its 2012 1M celebration montage. The fans who grew up on it are adults now, and most of them left. The Odyssey is a story about coming home after years away, so we built the road home.

**What it does.**
- **The Bard (ElevenLabs Agents):** a 60-second voice conversation that classifies you as Odysseus (returning) or Telemachus (new), then shows your Odyssey Map.
- **The Bard Sings:** a personal lore episode, narrated, played over FaZe's own YouTube clip at the right timestamp.
- **The Oracle (Gemini vision, with a local Ollama model as backup):** show the Oracle old merch (Argos Remembers) or a trickshot (Bow Trial), on the web camera or over FaceTime. It names the item, dates it to an era with the clue it used, and scores your shot.
- **The Siren (Chrome extension):** shows lore on FaZe YouTube and Twitch videos and lets you collect relics.
- **Athena:** a guide on every page that walks each fan through a 7-step quest and takes them to the next step.
- **Hub:** Odyssey Map with era videos from FaZe's channel, relics, Daily Omen, shareable recap, Suitors leaderboard.
- **Tiers:** more relics unlock rewards (badges, wallpapers, early drops, limited merch); the $4.99 Odyssey Pass unlocks a meet & greet with a FaZe member.
- **War Room:** the CTO dashboard, showing Pass, Sponsored Trials and Era Drops revenue and the reactivation metric.

**How we built it.** Next.js and Tailwind for the Hub; FastAPI on Vultr for the API; the Siren as a Manifest V3 extension; Gemini for the Oracle's vision, Bard scripts and embeddings, with a local Ollama vision model as backup; ElevenLabs for the Bard voice; MongoDB Atlas for lore vector search; Tiger Data (Postgres) for events and the War Room aggregates.

**How we used each sponsor tech.**
- **Chert:** the FaceTime Oracle (a LiveKit agent on the call) and iMessage follow-ups. *(Only claim this if Chert keys are live for the demo.)*
- **ElevenLabs:** the Bard's voice agent and episode narration.
- **Gemini:** multimodal Oracle judging (frames), lore RAG, and the Bow Trial safety check.
- **Tiger Data:** the events hypertable and continuous aggregates behind the War Room.
- **MongoDB Atlas:** lore documents and vector search.
- **Vultr:** hosts the API behind HTTPS.
- **GoDaddy:** the domain.

**Challenges.** Keeping the demo alive when a sponsor service is slow or down: every call has a canned fallback, so the Oracle never goes silent.

**Accomplishments.** A working end-to-end path from the Bard to the map, the Oracle verdict to a relic, and the Siren collect to Drachmae.

**What's next.** Real fan accounts, a moderated Bow Trial leaderboard, and FaZe's own brand assets.

**Privacy.** See docs/PRIVACY_NOTES.md. Oracle frames are not stored; phone numbers are keyed-hashed.

**Before submitting:** fill in the demo video (≤2 min), the architecture image, and screenshots of all four surfaces; and confirm each sponsor line above matches what the demo actually uses.

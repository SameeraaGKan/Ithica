// Defaults. Every value can be changed at runtime in the side panel's ⚙ settings
// (saved to chrome.storage.local), so nobody has to rebuild the extension at the judging table.
export const DEFAULTS = {
  apiBase: "https://ithaca-api-45jt.onrender.com", // the deployed API; opening the Hub switches it to the Hub's own
  webBase: "https://new-ithaca.vercel.app",         // Ithaca Hub (for "Ask the Bard" and profile links)
  fan: "demo_odysseus",               // fan_id sent to /siren/collect; opening the Hub switches it to your fan
  apiTimeoutMs: 8000                  // Render can take a few seconds; after this, fall back to bundled lore so the demo never stalls
};

// FaZe members whose channels don't say "FaZe" any more. Matched against the channel NAME exactly
// (case-insensitive, an optional "FaZe" prefix and punctuation removed), so "Swagg" counts but "SwaggerGaming" doesn't.
export const FAZE_MEMBER_NAMES = [
  "rug", "banks", "apex", "adapt", "swagg", "jarvis", "kaysan", "lacy", "stable ronaldo", "silky", "jason",
  "temperrr", "clipz", "teeqo", "sensei", "censor", "megga", "replays", "nickmercs", "booya", "santana",
];

// Channels treated as FaZe even if the name check misses (lower-case handles / Twitch logins).
export const FAZE_CHANNELS = [
  "@fazeclan", "@faze", "@fazerug", "@fazeadapt", "@fazeapex", "@fazeswagg", "@fazebanks", "@fazetemperrr",
  "fazeclan", "faze", "swagg", "fazeswagg", "fazeapex", "fazeadapt"
];

export async function getSettings() {
  const saved = await chrome.storage.local.get(["apiBase", "webBase", "fan"]);
  return { ...DEFAULTS, ...saved };
}

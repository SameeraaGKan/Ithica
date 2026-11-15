// Defaults. Every value can be changed at runtime in the side panel's ⚙ settings
// (saved to chrome.storage.local), so nobody has to rebuild the extension at the judging table.
export const DEFAULTS = {
  apiBase: "http://localhost:8000",   // switch to https://api.<your-domain> once Vultr + Caddy are up
  webBase: "http://localhost:3000",   // Ithaca Hub (for "Ask the Bard" and profile links)
  fan: "demo_odysseus",               // fan_id sent to /siren/collect (backend creates the fan if new)
  apiTimeoutMs: 2500                  // after this, fall back to bundled lore so the demo never stalls
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

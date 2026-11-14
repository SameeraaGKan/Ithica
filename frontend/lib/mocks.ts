// Seeded demo data so every page renders even when the backend is down.
// War Room data is SIMULATED and labeled as such in the UI.
import { ERAS } from "./eras";
import type {
  ClassifyResult,
  EraId,
  LeaderboardRow,
  Odyssey,
  OracleMode,
  OracleVerdict,
  Relic,
  WarroomMetrics,
} from "./types";

export const DEMO_FAN_ID = process.env.NEXT_PUBLIC_DEMO_FAN_ID || "demo_odysseus";

// Deterministic PRNG so the charts look the same on every reload.
function rng(seed: number) {
  return () => {
    seed = (seed * 1664525 + 1013904223) % 4294967296;
    return seed / 4294967296;
  };
}

const ALL_RELICS: Relic[] = [
  { id: "r-first-montage", era: "2010_trickshots", name: "The First Montage", rarity: "legendary" },
  { id: "r-360-noscope", era: "2010_trickshots", name: "360 No-Scope", rarity: "rare" },
  { id: "r-the-rug", era: "2013_rug", name: "The Rug", rarity: "legendary" },
  { id: "r-house-key", era: "2013_rug", name: "House Key", rarity: "common" },
  { id: "r-nuke-badge", era: "2020_nuke", name: "Nuke Badge", rarity: "rare" },
  { id: "r-warzone-drop", era: "2020_nuke", name: "Warzone Drop", rarity: "common" },
  { id: "r-boardroom", era: "2022_snoop", name: "Boardroom Seat", rarity: "rare" },
  { id: "r-homecoming", era: "today", name: "Homecoming", rarity: "legendary" },
];

// Mock mode is in-memory per tab; drachmae goes up when the demo "collect" fires.
const mockState = {
  drachmae: 340,
  earned: new Set(["r-first-montage", "r-the-rug", "r-homecoming"]),
  entry: "2013_rug" as EraId, // set by mockClassify so the map matches what the fan said
};

export function mockOdyssey(fanId: string): Odyssey {
  const telemachus = fanId.includes("telemachus");
  const entry: EraId = telemachus ? "today" : mockState.entry;
  const episodes = [
    {
      id: "ep-1",
      title: telemachus ? "Why the name matters" : `You were there: the ${ERAS.find((e) => e.id === entry)?.label} era`,
      era: entry,
      // Drop a pre-generated ElevenLabs file at public/audio/demo-episode.mp3
      audio_url: "/audio/demo-episode.mp3",
      // Person D fills real FaZe video IDs + timestamps from the lore JSON.
      video_id: "",
      start_s: 0,
      end_s: 90,
    },
    { id: "ep-2", title: "The Nuke Squad rises", era: "2020_nuke" as EraId, audio_url: "", video_id: "", start_s: 0, end_s: 75 },
  ];
  return {
    fan: {
      id: fanId,
      handle: telemachus ? "NewBlood" : "OG_Scoper",
      path: telemachus ? "telemachus" : "odysseus",
      entry_era: entry,
      games: telemachus ? ["Fortnite", "Valorant"] : ["Call of Duty"],
      drachmae: mockState.drachmae,
    },
    relics: ALL_RELICS.filter((r) => mockState.earned.has(r.id)).map((r) => ({
      ...r,
      earned_at: new Date().toISOString(),
      via: "web" as const,
    })),
    locked_relics: ALL_RELICS.filter((r) => !mockState.earned.has(r.id)),
    next_episode: episodes[0],
    episodes,
  };
}

export function mockCollect(relicId?: string) {
  mockState.drachmae += 25;
  const next = relicId ?? ALL_RELICS.find((r) => !mockState.earned.has(r.id))?.id;
  if (next) mockState.earned.add(next);
}

export function mockClassify(answers: string): ClassifyResult {
  const a = answers.toLowerCase();
  const year = Number(a.match(/20(0\d|1\d|2\d)/)?.[0] ?? 0);
  if (!year || year >= 2023 || /new|just|never|recent/.test(a)) {
    return { fan_id: "demo-telemachus", path: "telemachus", entry_era: "today" };
  }
  const entry: EraId = year < 2013 ? "2010_trickshots" : year < 2020 ? "2013_rug" : year < 2022 ? "2020_nuke" : "2022_snoop";
  mockState.entry = entry;
  return { fan_id: DEMO_FAN_ID, path: "odysseus", entry_era: entry };
}

// Canned verdicts double as the "never dead air" fallback when Gemini is slow.
export function mockVerdict(mode: OracleMode): OracleVerdict {
  if (mode === "argos") {
    return {
      verdict: "Argos remembers. That relic is from the Rug Era, 2014. Twenty years the road, and still you wear the colors. Welcome home, Odysseus.",
      era: "2013_rug",
      confidence: 0.82,
      relic: ALL_RELICS[3],
      drachmae_awarded: 50,
    };
  }
  return {
    verdict: "The bow is strung. Clean flick, late spin, the shot lands. The Oracle scores it 87. The suitors tremble.",
    score: 87,
    reasons: ["Clean 360 rotation", "Hit on the final frame", "Good map choice"],
    drachmae_awarded: 87,
  };
}

export function mockLeaderboard(): LeaderboardRow[] {
  const names = ["OG_Scoper", "RugBurn", "NukeTown", "Telemachus_99", "TrickshotTom", "SirenSong", "NoScopeNell", "IthacaBound", "SuitorSlayer", "BowStringer"];
  const r = rng(7);
  return names
    .map((handle, i) => ({
      rank: 0,
      fan_id: `fan-${i}`,
      handle,
      path: (["Telemachus_99", "SirenSong", "IthacaBound"].includes(handle) ? "telemachus" : "odysseus") as LeaderboardRow["path"],
      drachmae: Math.round(400 + r() * 2200),
      best_trial_score: Math.round(55 + r() * 44),
    }))
    .sort((a, b) => b.drachmae - a.drachmae)
    .map((row, i) => ({ ...row, rank: i + 1 }));
}

export function mockWarroom(): WarroomMetrics {
  const r = rng(42);
  const days = 30;
  const today = new Date();
  const daily = Array.from({ length: days }, (_, i) => {
    const d = new Date(today);
    d.setDate(today.getDate() - (days - 1 - i));
    const growth = 1 + i / 18;
    const weekend = [0, 6].includes(d.getDay()) ? 1.25 : 1;
    return {
      day: d.toISOString().slice(0, 10),
      pass_cents: Math.round((18000 + r() * 6000) * growth * weekend),
      sponsored_cents: i < 9 ? 0 : Math.round((25000 + r() * 9000) * (1 + (i - 9) / 25)),
      drops_cents: i % 7 === 3 ? Math.round(40000 + r() * 30000) : Math.round(r() * 6000),
      daily_actives: Math.round((2200 + r() * 500) * growth * weekend),
      reactivated: Math.round((140 + r() * 60) * growth),
    };
  });
  const last = daily[days - 1];
  return {
    simulated: true,
    generated_at: new Date().toISOString(),
    kpis: {
      reactivated_fans: daily.reduce((s, d) => s + d.reactivated, 0),
      new_fan_activation: 41.6,
      daily_actives: last.daily_actives,
      trial_entries: 3182,
      pass_conversions: 1247,
      sponsored_impressions: 486000,
    },
    kpi_deltas: {
      reactivated_fans: 18.2,
      new_fan_activation: 4.1,
      daily_actives: 12.7,
      trial_entries: 22.5,
      pass_conversions: 9.3,
      sponsored_impressions: 31.0,
    },
    daily,
    funnel: [
      { stage: "Talked to the Bard", count: 18400 },
      { stage: "Odyssey Map revealed", count: 15100 },
      { stage: "First relic", count: 11250 },
      { stage: "Weekly Bow Trial", count: 3182 },
      { stage: "Odyssey Pass", count: 1247 },
    ],
    era_demand: ERAS.filter((e) => e.id !== "today").map((e) => ({
      era: e.id,
      label: `${e.year} ${e.label}`,
      waitlist: Math.round(800 + r() * 4200),
    })),
  };
}

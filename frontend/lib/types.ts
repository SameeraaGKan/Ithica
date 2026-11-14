// Shapes the frontend expects from the FastAPI backend (person A).
// Agree on these early — they mirror the data model + API surface in the plan.

export type EraId = "2010_trickshots" | "2013_rug" | "2020_nuke" | "2022_snoop" | "today";
export type FanPath = "odysseus" | "telemachus";

export interface EraInfo {
  id: EraId;
  year: string;
  label: string;
  blurb: string;
}

export interface Fan {
  id: string;
  handle: string;
  path: FanPath;
  entry_era: EraId;
  games: string[];
  drachmae: number;
}

export interface Relic {
  id: string;
  era: EraId;
  name: string;
  rarity: "common" | "rare" | "epic" | "legendary";
  art_url?: string;
  earned_at?: string;
  via?: "web" | "ext" | "facetime" | "imessage";
}

export interface Episode {
  id: string;
  title: string;
  era: EraId;
  audio_url: string; // ElevenLabs narration
  video_id: string; // FaZe's own YouTube video, embedded, never re-hosted
  start_s: number;
  end_s: number;
  script?: string;
}

// GET /odyssey/:fanId
export interface Odyssey {
  fan: Fan;
  relics: Relic[]; // earned
  locked_relics: Relic[]; // still to collect (drives Era Drops)
  next_episode: Episode | null;
  episodes: Episode[];
}

// POST /onboard/classify
export interface ClassifyResult {
  fan_id: string;
  path: FanPath;
  entry_era: EraId;
}

// POST /oracle/frame
export type OracleMode = "argos" | "bow_trial";
export interface OracleVerdict {
  verdict: string; // spoken text
  era?: EraId;
  confidence?: number;
  score?: number; // bow trial 0-100
  reasons?: string[];
  relic?: Relic;
  drachmae_awarded?: number;
}

export interface LeaderboardRow {
  rank: number;
  fan_id: string;
  handle: string;
  path: FanPath;
  drachmae: number;
  best_trial_score: number;
}

// GET /warroom/metrics
export interface WarroomMetrics {
  simulated: boolean;
  generated_at: string;
  kpis: {
    reactivated_fans: number;
    new_fan_activation: number; // %
    daily_actives: number;
    trial_entries: number;
    pass_conversions: number;
    sponsored_impressions: number;
  };
  kpi_deltas: Partial<Record<keyof WarroomMetrics["kpis"], number>>; // % vs previous week
  daily: {
    day: string; // YYYY-MM-DD
    pass_cents: number;
    sponsored_cents: number;
    drops_cents: number;
    daily_actives: number;
    reactivated: number;
  }[];
  funnel: { stage: string; count: number }[];
  era_demand: { era: EraId; label: string; waitlist: number }[];
}

export type DataSource = "live" | "mock";
export interface Sourced<T> {
  data: T;
  source: DataSource;
}

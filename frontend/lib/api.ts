// One API client for the whole Hub. Every call tries the real backend and falls back
// to seeded mocks, so the demo never shows an empty or broken page.
//
// The backend (backend/app/schemas.py) is the contract shared with the Siren extension and the
// voice agent, so this file adapts its responses to the Hub's types in lib/types.ts. Pages and
// components only ever see the Hub's shapes.
import { eraById } from "./eras";
import {
  mockClassify,
  mockCollect,
  mockLeaderboard,
  mockOdyssey,
  mockVerdict,
  mockWarroom,
} from "./mocks";
import type {
  ClassifyResult,
  EraId,
  Episode,
  LeaderboardRow,
  Odyssey,
  OracleMode,
  OracleVerdict,
  Relic,
  Sourced,
  WarroomMetrics,
} from "./types";

export const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");
const TIMEOUT_MS = 6000; // plan: canned fallback if Gemini/backend is slower than 6s
const ORACLE_TIMEOUT_MS = 12000; // the backend already answers with a canned verdict after 6s of Gemini
const EPISODE_TIMEOUT_MS = 30000; // first generation = Gemini script + ElevenLabs audio; cached after

// ---------------------------------------------------------------- backend → Hub adapters
const ERA_IN: Record<string, EraId> = {
  "2010_trickshots": "2010_trickshots",
  "2013_rug_era": "2013_rug",
  "2020_nuke_squad": "2020_nuke",
  "2022_snoop": "2022_snoop",
  today: "today",
};
const ERA_OUT: Record<EraId, string> = {
  "2010_trickshots": "2010_trickshots",
  "2013_rug": "2013_rug_era",
  "2020_nuke": "2020_nuke_squad",
  "2022_snoop": "2022_snoop",
  today: "today",
};
const eraIn = (e?: string | null): EraId => ERA_IN[e ?? ""] ?? "today";

/* eslint-disable @typescript-eslint/no-explicit-any */
const relicIn = (r: any): Relic => ({
  id: r.id,
  era: eraIn(r.era),
  name: r.name,
  rarity: r.rarity,
  art_url: r.art_url ?? undefined,
  earned_at: r.earned_at ?? undefined,
  via: r.via && r.via !== "seed" ? r.via : undefined,
});

const episodeIn = (ep: any): Episode => {
  const cue = (ep.cues ?? []).find((c: any) => c.video_id) ?? ep.cues?.[0] ?? {};
  const start = cue.start_s ?? 0;
  return {
    id: ep.episode_id,
    title: ep.title,
    era: eraIn(ep.era),
    audio_url: ep.audio_url ?? "",
    video_id: cue.video_id ?? "",
    start_s: start,
    end_s: cue.end_s ?? start + 90,
    script: ep.script,
  };
};

// ---------------------------------------------------------------- transport
async function raw(path: string, init?: RequestInit, timeoutMs = TIMEOUT_MS): Promise<any> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: ctrl.signal,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
    if (!res.ok) throw new Error(`${path} -> ${res.status}`);
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

async function call<T>(
  path: string,
  init: RequestInit | undefined,
  fallback: () => T,
  adapt: (data: any) => T = (d) => d as T,
  timeoutMs = TIMEOUT_MS,
): Promise<Sourced<T>> {
  if (!API_BASE) return { data: fallback(), source: "mock" };
  try {
    return { data: adapt(await raw(path, init, timeoutMs)), source: "live" };
  } catch (err) {
    console.warn("[ithaca] falling back to mock:", err);
    return { data: fallback(), source: "mock" };
  }
}

// The map page polls every 3s; generate each era/path episode once per page load, not per poll.
const episodeCache = new Map<string, Promise<Episode | null>>();
function episodeFor(era: string, path: string): Promise<Episode | null> {
  const key = `${era}|${path}`;
  if (!episodeCache.has(key)) {
    // no fan_id on purpose: polling must not log an episode_play (and pay Drachmae) every 3s
    const p = raw("/bard/episode", { method: "POST", body: JSON.stringify({ era, path, voice: true }) }, EPISODE_TIMEOUT_MS)
      .then(episodeIn)
      .catch((err) => {
        console.warn("[ithaca] episode unavailable:", err);
        episodeCache.delete(key); // retry on a later poll
        return null;
      });
    episodeCache.set(key, p);
  }
  return episodeCache.get(key)!;
}

export const api = {
  async odyssey(fanId: string): Promise<Sourced<Odyssey>> {
    if (!API_BASE) return { data: mockOdyssey(fanId), source: "mock" };
    let o: any;
    try {
      o = await raw(`/odyssey/${encodeURIComponent(fanId)}`);
    } catch (err) {
      console.warn("[ithaca] falling back to mock:", err);
      return { data: mockOdyssey(fanId), source: "mock" };
    }
    const path = o.path ?? "telemachus";
    const ep = await episodeFor(o.next_episode?.era ?? o.entry_era ?? "today", path);
    return {
      source: "live",
      data: {
        fan: {
          id: o.fan_id,
          handle: o.handle ?? o.fan_id,
          path,
          entry_era: eraIn(o.entry_era),
          games: o.games ?? [],
          drachmae: o.drachmae ?? 0,
        },
        relics: (o.relics ?? []).map(relicIn),
        locked_relics: (o.locked_relics ?? []).map(relicIn),
        next_episode: ep,
        episodes: ep ? [ep] : [],
      },
    };
  },

  // The typed fallback on /onboard sends free text; the backend classifies it (Gemini, or rules offline).
  classify: (answers: string) =>
    call<ClassifyResult>(
      "/onboard/classify",
      { method: "POST", body: JSON.stringify({ transcript: answers }) },
      () => mockClassify(answers),
      (r) => ({ fan_id: r.fan_id, path: r.path, entry_era: eraIn(r.entry_era) }),
    ),

  oracleFrame: (fanId: string, mode: OracleMode, imageBase64: string) =>
    call<OracleVerdict>(
      "/oracle/frame",
      { method: "POST", body: JSON.stringify({ fan_id: fanId, mode, image_b64: imageBase64, source: "web" }) },
      () => mockVerdict(mode),
      (v) => ({
        verdict: v.spoken,
        era: v.era ? eraIn(v.era) : undefined,
        confidence: v.confidence,
        score: v.score ?? undefined,
        reasons: v.reasons,
        relic: v.relic ? relicIn(v.relic) : undefined,
        drachmae_awarded: v.drachmae_awarded,
      }),
      ORACLE_TIMEOUT_MS,
    ),

  // The Suitors = this week's Bow Trial leaderboard.
  leaderboard: () =>
    call<LeaderboardRow[]>("/trials/leaderboard?limit=20", undefined, mockLeaderboard, (r) =>
      (r.suitors ?? []).map((s: any) => ({
        rank: s.rank,
        fan_id: s.fan_id,
        handle: s.handle,
        path: s.path ?? "telemachus",
        drachmae: s.drachmae ?? 0,
        best_trial_score: s.score ?? 0,
      })),
    ),

  warroom: () =>
    call<WarroomMetrics>("/warroom/metrics", undefined, mockWarroom, (m) => {
      const t = m.totals ?? {};
      const daily: any[] = m.daily ?? [];
      const sum = (rows: any[], k: string) => rows.reduce((a, r) => a + (r[k] ?? 0), 0);
      const last = daily.slice(-7);
      const prev = daily.slice(-14, -7);
      const delta = (k: string) => {
        const p = sum(prev, k);
        return p ? Math.round(((sum(last, k) - p) / p) * 1000) / 10 : 0;
      };
      const onboarded = (t.new_fans ?? 0) + (t.reactivated_fans ?? 0);
      return {
        simulated: !!m.simulated,
        generated_at: m.generated_at ?? new Date().toISOString(),
        kpis: {
          reactivated_fans: t.reactivated_fans ?? 0,
          new_fan_activation: onboarded ? ((t.new_fans ?? 0) / onboarded) * 100 : 0,
          daily_actives: t.dau_today ?? 0,
          trial_entries: t.trial_entries ?? 0,
          pass_conversions: t.pass_conversions ?? 0,
          sponsored_impressions: t.sponsored_impressions ?? 0,
        },
        kpi_deltas: {
          reactivated_fans: delta("reactivated"),
          daily_actives: delta("active_fans"),
          trial_entries: delta("trial_entries"),
          sponsored_impressions: delta("sponsored_impressions"),
        },
        daily: daily.map((d) => ({
          day: d.day,
          pass_cents: d.pass_cents ?? 0,
          sponsored_cents: d.sponsored_cents ?? 0,
          drops_cents: d.drops_cents ?? 0,
          daily_actives: d.active_fans ?? 0,
          reactivated: d.reactivated ?? 0,
        })),
        funnel: m.funnel ?? [],
        era_demand: Object.entries(m.era_drop_demand ?? {}).map(([era, n]) => ({
          era: eraIn(era),
          label: eraById(eraIn(era)).label,
          waitlist: n as number,
        })),
      };
    }),

  // Used for the demo when the Siren extension isn't connected; the extension itself
  // calls POST /siren/collect directly. No relicId = the fan's next uncollected relic.
  collect: (fanId: string, relicId?: string) =>
    call<{ ok: boolean }>(
      "/siren/collect",
      { method: "POST", body: JSON.stringify({ fan_id: fanId, relic_id: relicId }) },
      () => {
        mockCollect(relicId);
        return { ok: true };
      },
      () => ({ ok: true }),
    ),

  // Part B: ask the backend how to connect the Bard voice agent. It pre-creates the fan and returns
  // mode "signed" (signed_url), "public" (agent_id) or "unconfigured" (use the typed path).
  async bardSession(handle?: string): Promise<{
    mode: "signed" | "public" | "unconfigured";
    signed_url: string | null;
    agent_id: string | null;
    fan_id: string;
    dynamic_variables: Record<string, string>;
  } | null> {
    if (!API_BASE) return null;
    try {
      return await raw("/bard/agent/session", { method: "POST", body: JSON.stringify({ handle: handle ?? null }) });
    } catch (err) {
      console.warn("[ithaca] bard session unavailable:", err);
      return null;
    }
  },

  // Odyssey Pass + Era Drops (mocked payment on the backend, but logged so the War Room counts it).
  checkout: (fanId: string, sku = "odyssey_pass") =>
    call<{ ok: boolean }>(
      `/pass/checkout?fan_id=${encodeURIComponent(fanId)}&sku=${encodeURIComponent(sku)}`,
      { method: "POST" },
      () => ({ ok: true }),
    ),
};

export { ERA_OUT };

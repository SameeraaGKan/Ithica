// One API client for the whole Hub. Every call tries the real backend and falls back
// to seeded mocks, so the demo never shows an empty or broken page.
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
  LeaderboardRow,
  Odyssey,
  OracleMode,
  OracleVerdict,
  Sourced,
  WarroomMetrics,
} from "./types";

export const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");
const TIMEOUT_MS = 6000; // plan: canned fallback if Gemini/backend is slower than 6s

async function call<T>(path: string, init: RequestInit | undefined, fallback: () => T): Promise<Sourced<T>> {
  if (!API_BASE) return { data: fallback(), source: "mock" };
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: ctrl.signal,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
    if (!res.ok) throw new Error(`${path} -> ${res.status}`);
    return { data: (await res.json()) as T, source: "live" };
  } catch (err) {
    console.warn("[ithaca] falling back to mock:", err);
    return { data: fallback(), source: "mock" };
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  odyssey: (fanId: string) =>
    call<Odyssey>(`/odyssey/${encodeURIComponent(fanId)}`, undefined, () => mockOdyssey(fanId)),

  classify: (answers: string) =>
    call<ClassifyResult>("/onboard/classify", { method: "POST", body: JSON.stringify({ answers }) }, () =>
      mockClassify(answers),
    ),

  oracleFrame: (fanId: string, mode: OracleMode, imageBase64: string) =>
    call<OracleVerdict>(
      "/oracle/frame",
      { method: "POST", body: JSON.stringify({ fan_id: fanId, mode, image: imageBase64 }) },
      () => mockVerdict(mode),
    ),

  // Not in the plan's API surface yet — ask A to add GET /leaderboard (or derive from /warroom).
  leaderboard: () => call<LeaderboardRow[]>("/leaderboard", undefined, mockLeaderboard),

  warroom: () => call<WarroomMetrics>("/warroom/metrics", undefined, mockWarroom),

  // Used for the demo when the Siren extension isn't connected; the extension itself
  // calls POST /siren/collect directly.
  collect: (fanId: string, relicId?: string) =>
    call<{ ok: boolean }>(
      "/siren/collect",
      { method: "POST", body: JSON.stringify({ fan_id: fanId, relic_id: relicId, source: "web" }) },
      () => {
        mockCollect(relicId);
        return { ok: true };
      },
    ),
};

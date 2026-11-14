"use client";
import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";

// Health check page (plan: Robustness). Pings each endpoint the Hub depends on.
const CHECKS = ["/odyssey/demo-odysseus", "/warroom/metrics", "/leaderboard"];

export default function Health() {
  const [results, setResults] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!API_BASE) {
      setResults(Object.fromEntries(CHECKS.map((c) => [c, "mock mode (NEXT_PUBLIC_API_URL not set)"])));
      return;
    }
    CHECKS.forEach(async (path) => {
      const t0 = performance.now();
      try {
        const r = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
        setResults((s) => ({ ...s, [path]: `${r.status} · ${Math.round(performance.now() - t0)}ms` }));
      } catch (e) {
        setResults((s) => ({ ...s, [path]: `DOWN · ${String(e)}` }));
      }
    });
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="font-display text-3xl font-black">Health</h1>
      <p className="text-sm text-muted">API: {API_BASE || "(none, mock mode)"}</p>
      <div className="card space-y-2 font-mono text-sm">
        {CHECKS.map((c) => (
          <p key={c}>
            <span className="text-gold">{c}</span> → {results[c] ?? "…"}
          </p>
        ))}
      </div>
    </div>
  );
}

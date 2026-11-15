"use client";
import { motion } from "framer-motion";
import { useCallback } from "react";
import SourceBadge from "@/components/SourceBadge";
import { api } from "@/lib/api";
import { usePoll } from "@/lib/usePoll";

const MEDAL = ["🥇", "🥈", "🥉"];

export default function Leaderboard() {
  const fetcher = useCallback(() => api.leaderboard(), []);
  const { data, source } = usePoll(fetcher, 10000);

  return (
    <div className="space-y-6">
      <div className="hero-band flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">The Suitors</p>
          <h1 className="display text-5xl">Who strings the bow?</h1>
          <p className="mt-2 text-muted">Weekly rivals. Top Bow Trial clips get featured and scouted for FaZe Up.</p>
        </div>
        <SourceBadge source={source} />
      </div>

      <div className="card overflow-x-auto p-0">
        <table className="w-full min-w-[520px] text-left text-sm">
          <thead className="border-b border-line text-xs uppercase tracking-widest text-muted">
            <tr>
              <th className="px-5 py-3">#</th>
              <th className="px-5 py-3">Suitor</th>
              <th className="px-5 py-3">Path</th>
              <th className="px-5 py-3 text-right">Best trial</th>
              <th className="px-5 py-3 text-right">Drachmae</th>
            </tr>
          </thead>
          <tbody>
            {(data ?? []).map((row, i) => (
              <motion.tr
                key={row.fan_id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
                className={`border-b border-line/60 ${i === 0 ? "bg-gold/10" : ""}`}
              >
                <td className="px-5 py-3 font-display text-lg">{MEDAL[i] ?? row.rank}</td>
                <td className="px-5 py-3 font-semibold">{row.handle}</td>
                <td className="px-5 py-3 capitalize text-muted">{row.path}</td>
                <td className="px-5 py-3 text-right">{row.best_trial_score}</td>
                <td className="px-5 py-3 text-right font-semibold text-gold">{row.drachmae.toLocaleString()}</td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

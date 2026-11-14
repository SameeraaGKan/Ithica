"use client";
import { AnimatePresence, motion } from "framer-motion";
import { eraById } from "@/lib/eras";
import type { Relic } from "@/lib/types";

const RARITY = {
  common: "border-line text-muted",
  rare: "border-sky-500/50 text-sky-300",
  epic: "border-purple-500/60 text-purple-300",
  legendary: "border-gold text-gold",
} as const;

const VIA_LABEL = { web: "Ithaca", ext: "Siren", facetime: "Oracle", imessage: "Daily Omen" } as const;

export default function RelicGrid({ earned, locked }: { earned: Relic[]; locked: Relic[] }) {
  return (
    <div className="card">
      <div className="flex items-baseline justify-between">
        <div>
          <p className="eyebrow">Relics</p>
          <h2 className="mt-1 font-display text-2xl font-bold">
            {earned.length} / {earned.length + locked.length} collected
          </h2>
        </div>
        <p className="text-xs text-muted">Complete an era to unlock its Era Drop</p>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <AnimatePresence>
          {earned.map((r) => (
            <motion.div
              key={r.id}
              layout
              initial={{ opacity: 0, scale: 0.6, rotate: -8 }}
              animate={{ opacity: 1, scale: 1, rotate: 0 }}
              transition={{ type: "spring", stiffness: 260, damping: 18 }}
              className={`rounded-xl border bg-gradient-to-b from-white/5 to-transparent p-3 ${RARITY[r.rarity]}`}
            >
              <div className="flex aspect-square items-center justify-center rounded-lg bg-black/40 text-4xl">
                {r.art_url ? <img src={r.art_url} alt="" className="h-full w-full rounded-lg object-cover" /> : "🏺"}
              </div>
              <p className="mt-2 text-sm font-semibold text-white">{r.name}</p>
              <p className="text-xs capitalize">
                {r.rarity} · {eraById(r.era).year}
                {r.via ? ` · ${VIA_LABEL[r.via]}` : ""}
              </p>
            </motion.div>
          ))}
          {locked.map((r) => (
            <div key={r.id} className="rounded-xl border border-dashed border-line p-3 opacity-50">
              <div className="flex aspect-square items-center justify-center rounded-lg bg-black/40 text-3xl grayscale">🔒</div>
              <p className="mt-2 text-sm font-semibold">???</p>
              <p className="text-xs text-muted">{eraById(r.era).year} · {eraById(r.era).label}</p>
            </div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}

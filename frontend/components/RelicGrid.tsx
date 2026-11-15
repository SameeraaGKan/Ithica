"use client";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { eraById } from "@/lib/eras";
import type { Relic } from "@/lib/types";

const RARITY = {
  common: "border-line text-muted",
  rare: "border-sky-500/50 text-sky-300",
  epic: "border-purple-500/60 text-purple-300",
  legendary: "border-gold text-gold",
} as const;

const VIA_LABEL = { web: "Ithaca", ext: "Siren", facetime: "Oracle", imessage: "Daily Omen" } as const;

// Columns match the grid classes below: 2 on phones, 4 from the `sm` breakpoint (640px) up.
function useColumns() {
  const [cols, setCols] = useState(4);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 640px)");
    const update = () => setCols(mq.matches ? 4 : 2);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return cols;
}

export default function RelicGrid({ earned, locked }: { earned: Relic[]; locked: Relic[] }) {
  // Start with 2 rows; every full row of relics you collect reveals one more row.
  const cols = useColumns();
  const rows = 2 + Math.floor(earned.length / cols);
  const lockedShown = locked.slice(0, Math.max(0, rows * cols - earned.length));
  const hidden = locked.length - lockedShown.length;
  return (
    <div className="card">
      <div className="flex items-baseline justify-between">
        <div>
          <p className="eyebrow">Relics</p>
          <h2 className="display mt-1 text-4xl">
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
          {lockedShown.map((r) => (
            <div key={r.id} className="group relative rounded-xl border border-dashed border-line p-3 opacity-50 transition hover:opacity-100 hover:border-faze/60">
              <div className="flex aspect-square items-center justify-center rounded-lg bg-black/40 text-3xl grayscale">🔒</div>
              <p className="mt-2 text-sm font-semibold group-hover:hidden">???</p>
              <p className="mt-2 hidden text-sm font-semibold text-white group-hover:block">{r.name}</p>
              <p className="text-xs text-muted">{eraById(r.era).year} · {eraById(r.era).label}</p>
              <div className="pointer-events-none absolute left-1/2 top-full z-10 mt-2 hidden w-56 -translate-x-1/2 rounded-xl border border-faze/60 bg-ink p-3 text-left shadow-xl group-hover:block">
                <p className="eyebrow">Unlock this relic</p>
                <p className="mt-1 text-sm font-semibold text-white">{r.name}</p>
                <p className="mt-1 text-xs capitalize text-muted">{r.rarity} · {eraById(r.era).year} {eraById(r.era).label}</p>
                <p className="mt-2 text-xs text-muted">Collect it through the Bard, the Oracle or the Siren to add it to your Odyssey.</p>
              </div>
            </div>
          ))}
        </AnimatePresence>
      </div>
      {hidden > 0 && (
        <p className="mt-4 text-center text-xs uppercase tracking-widest text-muted">
          +{hidden} more relic{hidden === 1 ? "" : "s"} to discover · collect {cols - (earned.length % cols)} more to reveal the next row
        </p>
      )}
    </div>
  );
}

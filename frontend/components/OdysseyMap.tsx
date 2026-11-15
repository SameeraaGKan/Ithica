"use client";
import { motion } from "framer-motion";
import { ERAS } from "@/lib/eras";
import type { EraId, FanPath } from "@/lib/types";

// The Odyssey Map: 5 eras on a voyage path, path draws in, fan's entry era pulses.
export default function OdysseyMap({
  entryEra,
  path,
  selected,
  onSelect,
}: {
  entryEra: EraId;
  path: FanPath;
  selected?: EraId;
  onSelect?: (era: EraId) => void;
}) {
  const W = 1000;
  const H = 220;
  const pts = ERAS.map((_, i) => ({ x: 80 + i * ((W - 160) / (ERAS.length - 1)), y: i % 2 === 0 ? 140 : 70 }));
  const d = pts.reduce((acc, p, i) => {
    if (i === 0) return `M ${p.x} ${p.y}`;
    const prev = pts[i - 1];
    const mx = (prev.x + p.x) / 2;
    return `${acc} C ${mx} ${prev.y}, ${mx} ${p.y}, ${p.x} ${p.y}`;
  }, "");
  const entryIdx = ERAS.findIndex((e) => e.id === entryEra);

  return (
    <div className="card overflow-hidden">
      <div className="flex items-baseline justify-between gap-4">
        <div>
          <p className="eyebrow">Your Odyssey Map</p>
          <h2 className="display mt-1 text-4xl">
            {path === "odysseus" ? "You were there." : "Here is where it began."}
          </h2>
        </div>
        <span className="rounded-full bg-faze/15 px-3 py-1 text-xs font-semibold text-faze">
          {path === "odysseus" ? "Odysseus · returning" : "Telemachus · new"}
        </span>
      </div>

      <div className="mt-4 overflow-x-auto">
        <svg viewBox={`0 0 ${W} ${H}`} className="min-w-[640px] w-full" role="img" aria-label="FaZe eras timeline">
          <motion.path
            d={d}
            fill="none"
            stroke="var(--color-gold)"
            strokeWidth={3}
            strokeDasharray="10 8"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 2.2, ease: "easeInOut" }}
          />
          {ERAS.map((era, i) => {
            const p = pts[i];
            const isEntry = i === entryIdx;
            const visited = i <= entryIdx || path === "telemachus";
            const labelY = p.y > 100 ? p.y + 45 : p.y - 52;
            return (
              <motion.g
                key={era.id}
                initial={{ opacity: 0, scale: 0.5 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.3 + i * 0.4, type: "spring" }}
                style={{ transformOrigin: `${p.x}px ${p.y}px`, cursor: onSelect ? "pointer" : undefined }}
                onClick={() => onSelect?.(era.id)}
              >
                {/* larger invisible hit area so the stop is easy to tap */}
                <circle cx={p.x} cy={p.y} r={44} fill="transparent" />
                {selected === era.id && (
                  <circle cx={p.x} cy={p.y} r={isEntry ? 27 : 20} fill="none" stroke="white" strokeWidth={2} strokeDasharray="4 4" />
                )}
                {isEntry && (
                  <motion.circle
                    cx={p.x}
                    cy={p.y}
                    r={22}
                    fill="var(--color-faze)"
                    initial={{ opacity: 0.6, scale: 1 }}
                    animate={{ opacity: [0.6, 0], scale: [1, 2.2] }}
                    transition={{ repeat: Infinity, duration: 1.8, delay: 2.4 }}
                    style={{ transformOrigin: `${p.x}px ${p.y}px` }}
                  />
                )}
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={isEntry ? 18 : 12}
                  fill={isEntry ? "var(--color-faze)" : visited ? "var(--color-gold)" : "var(--color-panel)"}
                  stroke="var(--color-gold)"
                  strokeWidth={2}
                />
                <text x={p.x} y={labelY} textAnchor="middle" className="fill-white font-display" fontSize={20} fontWeight={700}>
                  {era.year}
                </text>
                <text x={p.x} y={labelY + 20} textAnchor="middle" fill="var(--color-muted)" fontSize={14}>
                  {era.label}
                </text>
                {isEntry && (
                  <text x={p.x} y={p.y + 5} textAnchor="middle" fill="white" fontSize={14} fontWeight={800}>
                    YOU
                  </text>
                )}
              </motion.g>
            );
          })}
        </svg>
      </div>
      <p className="mt-2 text-sm text-muted">
        {(selected ? ERAS.find((e) => e.id === selected) : ERAS[Math.max(entryIdx, 0)])?.blurb}
        {onSelect && <span className="ml-2 text-xs text-faze">Tap any era to watch it.</span>}
      </p>
    </div>
  );
}

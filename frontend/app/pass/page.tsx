"use client";
import { motion } from "framer-motion";
import { useState } from "react";
import { api } from "@/lib/api";
import { DEMO_FAN_ID } from "@/lib/mocks";

const PERKS = [
  "Premium Bard episodes for every era",
  "Exclusive Oracle trials each week",
  "Early access to Era Drops (limited merch reprints)",
  "Season-exclusive legendary relic",
];

// Checkout is mocked for the demo (plan: purchases table, "mocked checkout").
export default function Pass() {
  const [state, setState] = useState<"idle" | "processing" | "done">("idle");

  return (
    <div className="mx-auto max-w-3xl space-y-8 py-6">
      <div className="hero-band text-center">
        <p className="eyebrow">Season 1 · The Return</p>
        <h1 className="display mt-2 text-6xl">Odyssey Pass</h1>
        <p className="mt-3 text-muted">Cheap, collectible, status. Your seat at the hearth in Ithaca.</p>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="card mx-auto max-w-md border-gold/60 bg-gradient-to-b from-gold/15 via-panel to-panel text-center"
      >
        <p className="display text-7xl text-gold">$4.99</p>
        <p className="text-sm text-muted">per season</p>
        <ul className="mt-6 space-y-3 text-left text-sm">
          {PERKS.map((p) => (
            <li key={p} className="flex gap-3">
              <span className="text-gold">✦</span>
              {p}
            </li>
          ))}
        </ul>
        {state === "done" ? (
          <motion.p initial={{ scale: 0.8 }} animate={{ scale: 1 }} className="mt-8 font-display text-xl text-gold">
            Welcome to the hearth. Your Pass is active.
          </motion.p>
        ) : (
          <button
            className="btn btn-gold mt-8 w-full py-3 text-base"
            disabled={state === "processing"}
            onClick={async () => {
              setState("processing");
              await Promise.all([api.checkout(DEMO_FAN_ID), new Promise((r) => setTimeout(r, 900))]);
              setState("done");
            }}
          >
            {state === "processing" ? "Processing…" : "Claim the Pass"}
          </button>
        )}
        <p className="mt-3 text-xs text-muted">Demo checkout: no payment is taken.</p>
      </motion.div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="card">
          <p className="eyebrow">Era Drops</p>
          <p className="mt-2 text-sm text-muted">Collect every relic in an era to unlock that era&apos;s merch reprint. Earned access, not a store link.</p>
        </div>
        <div className="card">
          <p className="eyebrow">Sponsored Trials</p>
          <p className="mt-2 text-sm text-muted">Brands sponsor a weekly Bow Trial with a branded relic and leaderboard.</p>
        </div>
      </div>
    </div>
  );
}

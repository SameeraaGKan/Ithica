"use client";
import { motion } from "framer-motion";
import { useCallback, useEffect, useState } from "react";
import SourceBadge from "@/components/SourceBadge";
import { api } from "@/lib/api";
import { DEMO_FAN_ID } from "@/lib/mocks";
import type { Reward, RewardsStatus } from "@/lib/types";

/*
  Tier system: the more relics you collect, the more you unlock.
  Traveler 1 · Sailor 5 · Hero 10 · Legend 20 relics. The meet & greet is unlocked by the Odyssey Pass ($4.99).
*/
export default function Tiers() {
  const [s, setS] = useState<RewardsStatus | null>(null);
  const [source, setSource] = useState<"live" | "mock">("mock");
  const [buying, setBuying] = useState(false);
  const [member, setMember] = useState("");
  const [note, setNote] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    const r = await api.rewards(DEMO_FAN_ID);
    setS(r.data);
    setSource(r.source);
  }, []);
  useEffect(() => {
    load();
    api.questMark(DEMO_FAN_ID, "tier"); // Athena: opening Tiers completes the journey
  }, [load]);

  if (!s) return <p className="py-20 text-center text-muted">Counting your relics…</p>;

  const ladder = s.rewards.filter((r) => !r.requires_pass);
  const meet = s.rewards.find((r) => r.requires_pass);
  const top = ladder[ladder.length - 1]?.relics_needed || 20;
  const pct = Math.min(100, (s.relics / top) * 100);

  const claim = async (r: Reward, who?: string) => {
    try {
      const c = await api.claimReward(DEMO_FAN_ID, r.id, who);
      setNote((n) => ({ ...n, [r.id]: c.message }));
      load();
    } catch (e) {
      setNote((n) => ({ ...n, [r.id]: e instanceof Error ? e.message : String(e) }));
    }
  };

  const buyPass = async () => {
    setBuying(true);
    await Promise.all([api.checkout(DEMO_FAN_ID), new Promise((res) => setTimeout(res, 900))]);
    await load();
    setBuying(false);
  };

  return (
    <div className="space-y-6">
      <div className="hero-band flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">The tier system</p>
          <h1 className="display text-5xl">{s.tier ? s.tier.name : "Unranked"}</h1>
          <p className="mt-2 text-muted">
            {s.relics} relic{s.relics === 1 ? "" : "s"} collected
            {s.next_tier ? ` · ${s.next_tier.relics_to_go} more to reach ${s.next_tier.name}` : " · every tier unlocked"}
          </p>
        </div>
        <SourceBadge source={source} />
      </div>

      {/* progress across the ladder */}
      <div className="card">
        <div className="relative h-3 w-full overflow-hidden rounded-full bg-white/10">
          <motion.div className="h-full rounded-full bg-faze" initial={{ width: 0 }} animate={{ width: `${pct}%` }} transition={{ duration: 0.8 }} />
        </div>
        <div className="relative mt-2 h-8">
          {ladder.map((r) => (
            <div
              key={r.id}
              className="absolute -translate-x-1/2 text-center text-xs"
              style={{ left: `${Math.min(95, Math.max(4, (r.relics_needed / top) * 100))}%` }}
            >
              <span className={r.unlocked ? "font-bold text-white" : "text-muted"}>{r.tier}</span>
              <span className="block text-[10px] text-muted">{r.relics_needed}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {ladder.map((r) => (
          <div key={r.id} className={`card ${r.unlocked ? "border-faze/50" : "opacity-70"}`}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="eyebrow">
                  {r.tier} · {r.relics_needed} relic{r.relics_needed === 1 ? "" : "s"}
                </p>
                <h3 className="display mt-1 text-2xl">{r.title}</h3>
              </div>
              <span className="text-2xl">{r.unlocked ? (r.claimed ? "✅" : "🔓") : "🔒"}</span>
            </div>
            <p className="mt-2 text-sm text-muted">{r.description}</p>
            {r.unlocked && !r.claimed && (
              <button className="btn btn-primary mt-4" onClick={() => claim(r)}>
                Claim
              </button>
            )}
            {!r.unlocked && (
              <p className="mt-4 text-xs text-muted">
                Collect {r.relics_needed - s.relics} more relic{r.relics_needed - s.relics === 1 ? "" : "s"} with the Siren, the Oracle or the Bow Trial.
              </p>
            )}
            {(note[r.id] || r.claim?.message) && <p className="mt-3 text-sm text-gold">{note[r.id] || r.claim?.message}</p>}
          </div>
        ))}
      </div>

      {meet && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="card border-gold/60 bg-gradient-to-br from-gold/15 via-panel to-panel"
        >
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-xl">
              <p className="eyebrow">Odyssey Pass · $4.99 / season</p>
              <h3 className="display mt-1 text-3xl">{meet.title}</h3>
              <p className="mt-2 text-sm text-muted">{meet.description}</p>
            </div>
            <span className="text-3xl">{meet.unlocked ? (meet.claimed ? "✅" : "🔓") : "🔒"}</span>
          </div>

          {!meet.unlocked && (
            <button className="btn btn-gold mt-5" onClick={buyPass} disabled={buying}>
              {buying ? "Processing…" : "Get the Odyssey Pass · $4.99"}
            </button>
          )}
          {meet.unlocked && !meet.claimed && (
            <div className="mt-5 flex flex-wrap items-center gap-2">
              <select
                value={member}
                onChange={(e) => setMember(e.target.value)}
                className="rounded-md border border-line bg-black/40 px-3 py-2 text-sm outline-none focus:border-faze"
              >
                <option value="">Pick your FaZe favorite…</option>
                {s.faze_members.map((m) => (
                  <option key={m} value={m}>
                    FaZe {m}
                  </option>
                ))}
              </select>
              <button className="btn btn-primary" disabled={!member} onClick={() => claim(meet, member)}>
                Enter the draw
              </button>
            </div>
          )}
          {(note[meet.id] || meet.claim?.message) && <p className="mt-3 text-sm text-gold">{note[meet.id] || meet.claim?.message}</p>}
          <p className="mt-3 text-xs text-muted">Demo checkout: no payment is taken.</p>
        </motion.div>
      )}
    </div>
  );
}

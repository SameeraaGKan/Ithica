"use client";
import { motion } from "framer-motion";
import { useCallback, useMemo } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import SourceBadge from "@/components/SourceBadge";
import { api } from "@/lib/api";
import type { WarroomMetrics } from "@/lib/types";
import { usePoll } from "@/lib/usePoll";

// War Room — CTO/Board dashboard. Backed by Tiger Data continuous aggregates via GET /warroom/metrics.
// This is the "how it earns" proof in the pitch (step 6, 2:20).

const C = { pass: "#d4af37", sponsored: "#e4002b", drops: "#e8e8e8", grid: "#2a2a2a", axis: "#9a9a9a" };
const usd = (cents: number) => `$${(cents / 100).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const compact = (n: number) => Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(n);
const tooltipStyle = { background: "#141414", border: "1px solid #2a2a2a", borderRadius: 12, color: "#f5f5f5" };

type KpiKey = keyof WarroomMetrics["kpis"];
const KPIS: { key: KpiKey; label: string; fmt: (n: number) => string }[] = [
  { key: "reactivated_fans", label: "Reactivated returning fans", fmt: compact },
  { key: "new_fan_activation", label: "New-fan activation", fmt: (n) => `${n.toFixed(1)}%` },
  { key: "daily_actives", label: "Daily actives", fmt: compact },
  { key: "trial_entries", label: "Bow Trial entries", fmt: compact },
  { key: "pass_conversions", label: "Pass conversions", fmt: compact },
  { key: "sponsored_impressions", label: "Sponsored-trial impressions", fmt: compact },
];

export default function WarRoom() {
  const fetcher = useCallback(() => api.warroom(), []);
  const { data, source } = usePoll(fetcher, 5000);

  const totals = useMemo(() => {
    if (!data) return null;
    const sum = (k: "pass_cents" | "sponsored_cents" | "drops_cents") => data.daily.reduce((s, d) => s + d[k], 0);
    const pass = sum("pass_cents");
    const sponsored = sum("sponsored_cents");
    const drops = sum("drops_cents");
    return { pass, sponsored, drops, all: pass + sponsored + drops };
  }, [data]);

  if (!data || !totals) return <div className="py-24 text-center text-muted">Opening the War Room…</div>;

  const series = data.daily.map((d) => ({ ...d, label: d.day.slice(5) }));
  const funnelMax = data.funnel[0]?.count || 1;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">War Room · Board view</p>
          <h1 className="font-display text-4xl font-black">How Ithaca earns</h1>
          <p className="mt-1 text-sm text-muted">Last 30 days · refreshes every 5s · updated {new Date(data.generated_at).toLocaleTimeString()}</p>
        </div>
        <div className="flex gap-2">
          {data.simulated && <SourceBadge source={source} simulated />}
          <SourceBadge source={source} />
        </div>
      </div>

      {/* KPI tiles */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {KPIS.map((k, i) => {
          const delta = data.kpi_deltas[k.key];
          return (
            <motion.div key={k.key} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }} className="card p-4">
              <p className="text-xs text-muted">{k.label}</p>
              <p className="mt-2 font-display text-2xl font-bold">{k.fmt(data.kpis[k.key])}</p>
              {delta != null && (
                <p className={`mt-1 text-xs font-semibold ${delta >= 0 ? "text-emerald-400" : "text-faze"}`}>
                  {delta >= 0 ? "▲" : "▼"} {Math.abs(delta).toFixed(1)}% wk/wk
                </p>
              )}
            </motion.div>
          );
        })}
      </div>

      {/* Revenue */}
      <div className="card">
        <div className="flex flex-wrap items-baseline justify-between gap-4">
          <div>
            <p className="eyebrow">Revenue · three lines</p>
            <p className="mt-1 font-display text-3xl font-black">{usd(totals.all)}</p>
          </div>
          <div className="flex flex-wrap gap-4 text-sm">
            <Stat color={C.pass} label="Odyssey Pass" value={usd(totals.pass)} />
            <Stat color={C.sponsored} label="Sponsored Trials" value={usd(totals.sponsored)} />
            <Stat color={C.drops} label="Era Drops" value={usd(totals.drops)} />
          </div>
        </div>
        <div className="mt-4 h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={series} margin={{ left: 8, right: 8, top: 8 }}>
              <CartesianGrid stroke={C.grid} vertical={false} />
              <XAxis dataKey="label" stroke={C.axis} tickLine={false} fontSize={12} minTickGap={24} />
              <YAxis stroke={C.axis} tickLine={false} axisLine={false} fontSize={12} tickFormatter={(v) => usd(v)} width={64} />
              <Tooltip contentStyle={tooltipStyle} formatter={(v) => usd(Number(v))} />
              <Legend />
              <Line type="monotone" dataKey="pass_cents" name="Odyssey Pass" stroke={C.pass} strokeWidth={2.5} dot={false} />
              <Line type="monotone" dataKey="sponsored_cents" name="Sponsored Trials" stroke={C.sponsored} strokeWidth={2.5} dot={false} />
              <Line type="monotone" dataKey="drops_cents" name="Era Drops" stroke={C.drops} strokeWidth={2} dot={false} strokeDasharray="4 3" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Reactivation */}
        <div className="card">
          <p className="eyebrow">Odysseus returns</p>
          <h3 className="mt-1 font-display text-xl font-bold">Reactivated fans per day</h3>
          <div className="mt-4 h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={series} margin={{ left: 0, right: 8, top: 8 }}>
                <defs>
                  <linearGradient id="react" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={C.sponsored} stopOpacity={0.5} />
                    <stop offset="100%" stopColor={C.sponsored} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke={C.grid} vertical={false} />
                <XAxis dataKey="label" stroke={C.axis} tickLine={false} fontSize={12} minTickGap={24} />
                <YAxis stroke={C.axis} tickLine={false} axisLine={false} fontSize={12} width={40} />
                <Tooltip contentStyle={tooltipStyle} />
                <Area type="monotone" dataKey="reactivated" name="Reactivated" stroke={C.sponsored} fill="url(#react)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Funnel */}
        <div className="card">
          <p className="eyebrow">Funnel</p>
          <h3 className="mt-1 font-display text-xl font-bold">Bard to Pass</h3>
          <div className="mt-4 space-y-3">
            {data.funnel.map((f, i) => {
              const pct = (f.count / funnelMax) * 100;
              const conv = i > 0 ? (f.count / data.funnel[i - 1].count) * 100 : null;
              return (
                <div key={f.stage}>
                  <div className="flex justify-between text-sm">
                    <span>{f.stage}</span>
                    <span className="text-muted">
                      {f.count.toLocaleString()}
                      {conv != null && <span className="ml-2 text-xs text-gold">{conv.toFixed(0)}%</span>}
                    </span>
                  </div>
                  <div className="mt-1 h-3 overflow-hidden rounded-full bg-white/5">
                    <motion.div
                      className="h-full rounded-full bg-gradient-to-r from-faze to-gold"
                      initial={{ width: 0 }}
                      animate={{ width: `${pct}%` }}
                      transition={{ duration: 0.8, delay: i * 0.1 }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Era Drop demand */}
      <div className="card">
        <p className="eyebrow">Era Drops</p>
        <h3 className="mt-1 font-display text-xl font-bold">Merch drop demand by era (waitlist)</h3>
        <div className="mt-4 h-56">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.era_demand} margin={{ left: 0, right: 8, top: 8 }}>
              <CartesianGrid stroke={C.grid} vertical={false} />
              <XAxis dataKey="label" stroke={C.axis} tickLine={false} fontSize={12} />
              <YAxis stroke={C.axis} tickLine={false} axisLine={false} fontSize={12} width={48} tickFormatter={compact} />
              <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
              <Bar dataKey="waitlist" name="Waitlist" fill={C.pass} radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

function Stat({ color, label, value }: { color: string; label: string; value: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
      <span className="text-muted">{label}</span>
      <span className="font-semibold">{value}</span>
    </div>
  );
}

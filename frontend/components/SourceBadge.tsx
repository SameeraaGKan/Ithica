import type { DataSource } from "@/lib/types";

export default function SourceBadge({ source, simulated }: { source: DataSource; simulated?: boolean }) {
  if (simulated) {
    return (
      <span className="rounded-full border border-gold/60 bg-gold/10 px-3 py-1 text-xs font-semibold text-gold">
        Simulated data
      </span>
    );
  }
  return (
    <span
      className={`rounded-full px-3 py-1 text-xs font-semibold ${
        source === "live" ? "bg-emerald-500/15 text-emerald-400" : "bg-white/5 text-muted"
      }`}
      title={source === "live" ? "Connected to the Ithaca API" : "Backend unreachable or not set; showing seeded demo data"}
    >
      {source === "live" ? "● Live" : "○ Demo data"}
    </span>
  );
}

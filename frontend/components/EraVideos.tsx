"use client";
import { motion } from "framer-motion";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { eraById } from "@/lib/eras";
import type { EraId, EraVideo, FanPath } from "@/lib/types";

/*
  Map -> YouTube -> Siren -> relics -> Tiers, with the Oracle as the proof step.
  Each card opens a FaZe video from the selected era on YouTube, where the Siren extension shows the lore
  and lets the fan collect that moment's relic. The Oracle card asks them to prove they were there.
*/
export default function EraVideos({ era, fanId, path }: { era: EraId; fanId: string; path: FanPath }) {
  const [videos, setVideos] = useState<EraVideo[] | null>(null);
  const info = eraById(era);

  useEffect(() => {
    setVideos(null);
    api.eraVideos(era, fanId).then((r) => setVideos(r.data));
  }, [era, fanId]);

  return (
    <div id="era-videos" className="card scroll-mt-24">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <p className="eyebrow">
            Relive {info.year} · {info.label}
          </p>
          <h2 className="display mt-1 text-3xl">Watch the era</h2>
        </div>
        <p className="max-w-sm text-xs text-muted">
          Open a video on YouTube. The <span className="text-white">Siren</span> slides in with the story and the relic to collect.
        </p>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {videos === null &&
          Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-48 animate-pulse rounded-xl bg-white/5" />)}
        {videos?.map((v, i) => (
          <motion.a
            key={v.lore_id ?? v.url}
            href={v.url}
            target="_blank"
            rel="noreferrer"
            onClick={() => api.questMark(fanId, "era")}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            className="group overflow-hidden rounded-xl border border-line bg-black/30 transition hover:border-faze/60"
          >
            <div className="relative aspect-video bg-gradient-to-br from-faze/30 via-black to-black">
              {v.thumbnail ? (
                <img src={v.thumbnail} alt="" className="h-full w-full object-cover opacity-90 transition group-hover:opacity-100" />
              ) : (
                <div className="flex h-full items-center justify-center px-4 text-center">
                  <span className="display text-xl text-white/80">{v.title}</span>
                </div>
              )}
              <span className="absolute bottom-2 left-2 rounded bg-black/70 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white">
                {v.kind === "search" ? "Find on YouTube ↗" : "Watch on YouTube ↗"}
              </span>
              {v.relic && (
                <span
                  className={`absolute right-2 top-2 rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                    v.relic.collected ? "bg-gold text-ink" : "bg-faze text-white"
                  }`}
                >
                  {v.relic.collected ? "✓ Relic" : "🏺 Relic"}
                </span>
              )}
            </div>
            <div className="p-3">
              <p className="text-sm font-semibold text-white">{v.title}</p>
              <p className="mt-0.5 line-clamp-2 text-xs text-muted">
                {v.year ? `${v.year} · ` : ""}
                {v.summary}
              </p>
              {v.relic && !v.relic.collected && (
                <p className="mt-2 text-xs text-faze">Collect &ldquo;{v.relic.name}&rdquo; with the Siren</p>
              )}
            </div>
          </motion.a>
        ))}
        {videos?.length === 0 && <p className="text-sm text-muted">No videos for this era yet.</p>}
      </div>

      {/* The Oracle: prove you were there (returning fans) or earn your place (new fans) */}
      <div className="mt-5 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-faze/40 bg-faze/10 p-4">
        <div>
          <p className="eyebrow">The Oracle</p>
          <p className="mt-1 text-sm text-white">
            {path === "odysseus"
              ? `Were you really there? Show the Oracle your merch from the ${info.label} days and claim the era's relic.`
              : "No old merch? Show the Oracle your best trickshot and earn your place among the Suitors."}
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/oracle-cam?mode=argos&from=era-videos" className={`btn ${path === "odysseus" ? "btn-primary" : "btn-ghost"}`}>
            Show your merch
          </Link>
          <Link href="/oracle-cam?mode=bow_trial&from=era-videos" className={`btn ${path === "odysseus" ? "btn-ghost" : "btn-primary"}`}>
            Bow Trial
          </Link>
        </div>
      </div>
    </div>
  );
}

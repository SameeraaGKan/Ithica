"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { rememberFan } from "@/components/Athena";
import DailyOmen from "@/components/DailyOmen";
import DrachmaeCounter from "@/components/DrachmaeCounter";
import EraVideos from "@/components/EraVideos";
import EpisodePlayer from "@/components/EpisodePlayer";
import OdysseyMap from "@/components/OdysseyMap";
import RelicGrid from "@/components/RelicGrid";
import SourceBadge from "@/components/SourceBadge";
import { api } from "@/lib/api";
import { usePoll } from "@/lib/usePoll";
import type { EraId } from "@/lib/types";

// P1 shareable recap: renders a vertical clip of this fan's Odyssey on the backend.
function ShareRecap({ fanId }: { fanId: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const make = async () => {
    setBusy(true);
    const { data } = await api.recap(fanId);
    setUrl(data.video_url);
    setBusy(false);
  };
  return (
    <div className="card">
      <p className="eyebrow">Share your Odyssey</p>
      <p className="mt-2 text-sm text-muted">A 15-second vertical recap: your map, your Bard, your relics.</p>
      {url ? (
        <div className="mt-3 flex flex-wrap gap-2">
          <a href={url} target="_blank" rel="noreferrer" className="btn btn-gold">Open recap</a>
          <a href={url} download className="btn btn-ghost">Download</a>
        </div>
      ) : (
        <button className="btn btn-ghost mt-3" onClick={make} disabled={busy}>
          {busy ? "Rendering…" : "Make my recap"}
        </button>
      )}
    </div>
  );
}

export default function OdysseyPage() {
  const { fanId } = useParams<{ fanId: string }>();
  const fetcher = useCallback(() => api.odyssey(fanId), [fanId]);
  // Poll every 3s so Siren relic collects show up live on the Hub.
  const { data, source, refresh } = usePoll(fetcher, 3000);
  const [picked, setPicked] = useState<EraId | null>(null); // map stop the fan tapped (default: their entry era)
  useEffect(() => rememberFan(fanId), [fanId]); // Athena follows this fan
  const loaded = !!data;
  useEffect(() => {
    if (!loaded || !window.location.hash) return;
    const el = document.getElementById(window.location.hash.slice(1));
    if (el) setTimeout(() => el.scrollIntoView({ behavior: "smooth", block: "start" }), 150);
  }, [loaded]);

  if (!data) {
    return <div className="py-24 text-center font-display text-xl text-muted">The Bard is finding your place in the story…</div>;
  }

  const { fan } = data;
  return (
    <div className="space-y-6">
      <div className="hero-band flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="eyebrow">Welcome home</p>
          <h1 className="display text-5xl sm:text-6xl">{fan.handle}</h1>
          {fan.games.length > 0 && <p className="text-sm text-muted">Plays {fan.games.join(", ")}</p>}
        </div>
        <div className="flex items-center gap-3">
          <SourceBadge source={source} />
          <DrachmaeCounter value={fan.drachmae} />
        </div>
      </div>

      <OdysseyMap entryEra={fan.entry_era} path={fan.path} selected={picked ?? fan.entry_era} onSelect={setPicked} />
      <EraVideos era={picked ?? fan.entry_era} fanId={fan.id} path={fan.path} />

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-4 lg:col-span-3">
          <EpisodePlayer episode={data.next_episode} others={data.episodes} fanId={fan.id} />
          <DailyOmen fanId={fan.id} />
        </div>
        <div className="space-y-4 lg:col-span-2">
          <div id="bow-trial" className="card scroll-mt-24">
            <p className="eyebrow">This week&apos;s Bow Trial</p>
            <h3 className="display mt-1 text-2xl">String the bow</h3>
            <p className="mt-2 text-sm text-muted">
              Only the true king strings the bow. Show the Oracle your best trickshot and see where you land among the Suitors.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Link href="/oracle-cam?mode=bow_trial&from=bow-trial" className="btn btn-primary">
                Enter the trial
              </Link>
            </div>
          </div>
          <ShareRecap fanId={fan.id} />
          <div className="card border-gold/40 bg-gradient-to-br from-gold/10 to-transparent">
            <p className="eyebrow">Tiers · {data.relics.length} relics</p>
            <h3 className="display mt-1 text-2xl">More relics, more rewards</h3>
            <p className="mt-2 text-sm text-muted">Badges, wallpapers, early Era Drops and Legend-only merch. The Odyssey Pass unlocks a meet &amp; greet with your FaZe favorite.</p>
            <Link href="/tiers" className="btn btn-gold mt-4">
              See your tier
            </Link>
          </div>
          {source === "mock" && (
            <button
              className="btn btn-ghost w-full text-xs"
              onClick={async () => {
                await api.collect(fan.id);
                refresh();
              }}
              title="Stands in for the Siren extension when it isn't connected"
            >
              Simulate Siren relic collect
            </button>
          )}
        </div>
      </div>

      <RelicGrid earned={data.relics} locked={data.locked_relics} />
    </div>
  );
}

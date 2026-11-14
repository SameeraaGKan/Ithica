"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback } from "react";
import DrachmaeCounter from "@/components/DrachmaeCounter";
import EpisodePlayer from "@/components/EpisodePlayer";
import OdysseyMap from "@/components/OdysseyMap";
import RelicGrid from "@/components/RelicGrid";
import SourceBadge from "@/components/SourceBadge";
import { api } from "@/lib/api";
import { usePoll } from "@/lib/usePoll";

export default function OdysseyPage() {
  const { fanId } = useParams<{ fanId: string }>();
  const fetcher = useCallback(() => api.odyssey(fanId), [fanId]);
  // Poll every 3s so Siren relic collects show up live on the Hub.
  const { data, source, refresh } = usePoll(fetcher, 3000);

  if (!data) {
    return <div className="py-24 text-center font-display text-xl text-muted">The Bard is finding your place in the story…</div>;
  }

  const { fan } = data;
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="eyebrow">Welcome home</p>
          <h1 className="font-display text-3xl font-black sm:text-4xl">{fan.handle}</h1>
          {fan.games.length > 0 && <p className="text-sm text-muted">Plays {fan.games.join(", ")}</p>}
        </div>
        <div className="flex items-center gap-3">
          <SourceBadge source={source} />
          <DrachmaeCounter value={fan.drachmae} />
        </div>
      </div>

      <OdysseyMap entryEra={fan.entry_era} path={fan.path} />

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <EpisodePlayer episode={data.next_episode} others={data.episodes} />
        </div>
        <div className="space-y-4 lg:col-span-2">
          <div className="card">
            <p className="eyebrow">This week&apos;s Bow Trial</p>
            <h3 className="mt-1 font-display text-xl font-bold">String the bow</h3>
            <p className="mt-2 text-sm text-muted">
              Only the true king strings the bow. FaceTime the Oracle with your best trickshot and climb the Suitors board.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Link href="/oracle-cam?mode=bow_trial" className="btn btn-primary">
                Enter the trial
              </Link>
              <Link href="/leaderboard" className="btn btn-ghost">
                Suitors
              </Link>
            </div>
          </div>
          <div className="card border-gold/40 bg-gradient-to-br from-gold/10 to-transparent">
            <p className="eyebrow">Odyssey Pass</p>
            <h3 className="mt-1 font-display text-xl font-bold">Premium episodes + early Era Drops</h3>
            <p className="mt-2 text-sm text-muted">$4.99 / season. Exclusive Oracle trials and first access to era merch reprints.</p>
            <Link href="/pass" className="btn btn-gold mt-4">
              Get the Pass
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

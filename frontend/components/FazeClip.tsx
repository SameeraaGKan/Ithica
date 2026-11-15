"use client";
import { useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/api";

// Plays a FaZe clip inside the page with YouTube's official player and awards the relic after WATCH_S seconds.
// Only FaZe videos count: the API checks the video against the lore (is_faze) before any relic is given.
const WATCH_S = 30;
const LOAD_TIMEOUT_MS = 8000;

declare global {
  interface Window {
    YT?: any;
    onYouTubeIframeAPIReady?: () => void;
  }
}

let apiPromise: Promise<void> | null = null;
function loadYouTubeApi(): Promise<void> {
  if (window.YT?.Player) return Promise.resolve();
  if (!apiPromise) {
    apiPromise = new Promise((resolve, reject) => {
      const tag = document.createElement("script");
      tag.src = "https://www.youtube.com/iframe_api";
      tag.onerror = () => reject(new Error("YouTube player failed to load"));
      window.onYouTubeIframeAPIReady = () => resolve();
      document.head.appendChild(tag);
      setTimeout(() => reject(new Error("YouTube player timed out")), LOAD_TIMEOUT_MS);
    });
  }
  return apiPromise;
}

export default function FazeClip({
  videoId,
  start,
  end,
  fanId,
  muted = false,
}: {
  videoId: string;
  start: number;
  end: number;
  fanId: string;
  muted?: boolean; // the episode player mutes the clip so the Bard's narration is heard over it
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [watched, setWatched] = useState(0);
  const [earned, setEarned] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let player: any = null;
    let ticker: ReturnType<typeof setInterval> | null = null;
    let counted = 0;
    let done = false;

    const awardIfFaze = async () => {
      // Ask the lore whether this moment is FaZe, then award the relic for it.
      const ctxUrl = `${API_BASE}/siren/context?videoId=${encodeURIComponent(videoId)}&t=${start}&fan_id=${encodeURIComponent(fanId)}`;
      const ctx = await fetch(ctxUrl, { cache: "no-store" }).then((r) => r.json());
      if (!ctx.is_faze || !ctx.lore) return;
      const res = await fetch(`${API_BASE}/siren/collect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fan_id: fanId, video_id: videoId, t: start, lore_id: ctx.lore.id }),
      }).then((r) => r.json());
      setEarned(res.already_had ? `You already hold ${res.relic?.name ?? "this relic"}.` : `Relic earned: ${res.relic?.name ?? ""}`);
    };

    loadYouTubeApi()
      .then(() => {
        if (done || !hostRef.current) return;
        player = new window.YT.Player(hostRef.current, {
          videoId,
          playerVars: { start, end, rel: 0, modestbranding: 1, playsinline: 1, autoplay: 1, mute: muted ? 1 : 0 },
          events: {
            onStateChange: (e: any) => {
              const playing = e.data === window.YT.PlayerState.PLAYING;
              if (playing && !ticker) {
                ticker = setInterval(() => {
                  counted += 1;
                  setWatched(Math.min(counted, WATCH_S));
                  if (counted === WATCH_S) {
                    awardIfFaze().catch(() => setError("Could not reach the Oracle's records."));
                  }
                }, 1000);
              } else if (!playing && ticker) {
                clearInterval(ticker);
                ticker = null;
              }
            },
          },
        });
      })
      .catch((err) => setError(err.message));

    return () => {
      done = true;
      if (ticker) clearInterval(ticker);
      player?.destroy?.();
    };
  }, [videoId, start, end, fanId, muted]);

  // Fills its parent (the episode player's video box); the watch timer sits on top of the clip.
  return (
    <div className="relative h-full w-full">
      <div ref={hostRef} className="h-full w-full" />
      <span className="pointer-events-none absolute left-2 top-2 rounded bg-black/75 px-2 py-1 text-[11px] font-semibold text-white">
        {error ?? earned ?? (watched >= WATCH_S ? "Checking the lore…" : `Watch ${WATCH_S - watched}s more to earn the relic`)}
      </span>
    </div>
  );
}

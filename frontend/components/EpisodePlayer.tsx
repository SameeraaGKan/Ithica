"use client";
import { useState } from "react";
import { eraById } from "@/lib/eras";
import type { Episode } from "@/lib/types";

// The Bard Sings: FaZe's own YouTube video (embedded at timestamps, muted) + Bard narration on top.
export default function EpisodePlayer({ episode, others }: { episode: Episode | null; others: Episode[] }) {
  const [current, setCurrent] = useState<Episode | null>(episode);
  const [audioFailed, setAudioFailed] = useState(false);
  const [started, setStarted] = useState(false);

  if (!current) {
    return (
      <div className="card">
        <p className="eyebrow">The Bard Sings</p>
        <p className="mt-3 text-muted">The Bard is still composing your first episode…</p>
      </div>
    );
  }

  const src = current.video_id
    ? `https://www.youtube-nocookie.com/embed/${current.video_id}?start=${current.start_s}&end=${current.end_s}&mute=1&autoplay=${started ? 1 : 0}&rel=0&modestbranding=1`
    : null;

  return (
    <div className="card">
      <p className="eyebrow">The Bard Sings</p>
      <h2 className="display mt-1 text-3xl">{current.title}</h2>
      <p className="text-sm text-muted">
        {eraById(current.era).year} · {eraById(current.era).label} · {Math.round(current.end_s - current.start_s)}s
      </p>

      <div className="mt-4 aspect-video w-full overflow-hidden rounded-xl border border-line bg-black">
        {src ? (
          <iframe
            key={`${current.id}-${started}`}
            src={src}
            title={current.title}
            className="h-full w-full"
            allow="autoplay; encrypted-media; picture-in-picture"
            allowFullScreen
          />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 bg-gradient-to-br from-faze-dark/40 to-black text-center">
            <span className="font-display text-4xl text-gold">♪</span>
            <p className="max-w-xs text-sm text-muted">
              Video slot. Set <code className="text-gold">video_id</code> + timestamps from the lore DB to embed the real FaZe clip.
            </p>
          </div>
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        {!started && (
          <button className="btn btn-primary" onClick={() => setStarted(true)}>
            ▶ Play episode
          </button>
        )}
        {started && current.audio_url && !audioFailed && (
          <audio
            src={current.audio_url}
            autoPlay
            controls
            onError={() => setAudioFailed(true)}
            className="h-10 w-full max-w-md"
          />
        )}
        {started && (audioFailed || !current.audio_url) && (
          <p className="text-sm text-muted">
            Narration not generated yet. Drop the ElevenLabs file at <code className="text-gold">public/audio/demo-episode.mp3</code>.
          </p>
        )}
      </div>

      {others.length > 1 && (
        <div className="mt-5 border-t border-line pt-4">
          <p className="mb-2 text-xs uppercase tracking-widest text-muted">More episodes</p>
          <div className="flex flex-wrap gap-2">
            {others.map((ep) => (
              <button
                key={ep.id}
                onClick={() => {
                  setCurrent(ep);
                  setStarted(false);
                  setAudioFailed(false);
                }}
                className={`btn ${ep.id === current.id ? "btn-gold" : "btn-ghost"} px-3 py-1.5 text-xs`}
              >
                {ep.title}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

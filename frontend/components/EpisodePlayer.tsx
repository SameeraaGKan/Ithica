"use client";
import { motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { eraById } from "@/lib/eras";
import type { Episode } from "@/lib/types";

/*
  The Bard Sings: FaZe's own YouTube video (embedded at timestamps, muted) + Bard narration on top.
  - Narration: the ElevenLabs mp3 when the backend made one; otherwise the browser reads the script aloud.
  - Video: the real clip when the lore has a video_id; otherwise a Bard card + a link to find it on YouTube.
*/
export default function EpisodePlayer({
  episode,
  others,
  fanId,
}: {
  episode: Episode | null;
  others: Episode[];
  fanId?: string;
}) {
  const [current, setCurrent] = useState<Episode | null>(episode);
  const [audioFailed, setAudioFailed] = useState(false);
  const [started, setStarted] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [line, setLine] = useState(0);
  const utterRef = useRef<SpeechSynthesisUtterance | null>(null);

  // Episode arrives after the first poll: adopt it, and refresh if the backend later adds audio.
  useEffect(() => {
    if (episode && (!current || current.id === episode.id)) setCurrent(episode);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [episode]);

  useEffect(() => () => window.speechSynthesis?.cancel(), []);

  if (!current) {
    return (
      <div className="card">
        <p className="eyebrow">The Bard Sings</p>
        <p className="mt-3 text-muted">The Bard is composing your first episode…</p>
        <div className="mt-4 aspect-video w-full animate-pulse rounded-xl bg-white/5" />
      </div>
    );
  }

  const era = eraById(current.era);
  const sentences = (current.script || "").match(/[^.!?]+[.!?]+["”']?|\S[^.!?]*$/g)?.map((s) => s.trim()) ?? [];
  const useBrowserVoice = !current.audio_url || audioFailed;

  const speak = () => {
    if (!("speechSynthesis" in window) || !current.script) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(current.script);
    // a deeper, slower storyteller voice when the OS has one
    const voices = window.speechSynthesis.getVoices();
    u.voice =
      voices.find((v) => /Daniel|George|Arthur|Guy|Ryan|Male/i.test(v.name) && v.lang.startsWith("en")) ??
      voices.find((v) => v.lang.startsWith("en")) ??
      null;
    u.rate = 0.92;
    u.pitch = 0.82;
    let chars = 0;
    const bounds = sentences.map((s) => (chars += s.length + 1));
    u.onboundary = (e) => setLine(Math.max(0, bounds.findIndex((b) => e.charIndex < b)));
    u.onend = () => setSpeaking(false);
    u.onerror = () => setSpeaking(false);
    utterRef.current = u;
    setLine(0);
    setSpeaking(true);
    window.speechSynthesis.speak(u);
  };

  const play = () => {
    setStarted(true);
    if (fanId) api.questMark(fanId, "song"); // Athena: the Bard's song is heard
    if (useBrowserVoice) speak();
  };

  const stop = () => {
    window.speechSynthesis?.cancel();
    setSpeaking(false);
  };

  const src = current.video_id
    ? `https://www.youtube-nocookie.com/embed/${current.video_id}?start=${current.start_s}&end=${current.end_s}&mute=1&autoplay=${started ? 1 : 0}&rel=0&modestbranding=1`
    : null;

  return (
    <div id="bard-song" className="card scroll-mt-24">
      <p className="eyebrow">The Bard Sings</p>
      <h2 className="display mt-1 text-3xl">{current.title}</h2>
      <p className="text-sm text-muted">
        {era.year} · {era.label} · {Math.round(current.end_s - current.start_s)}s
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
          <div className="relative flex h-full flex-col justify-between bg-gradient-to-br from-faze-dark/50 via-black to-black p-5">
            <div className="flex items-start justify-between">
              <span className="display text-6xl text-white/10">{era.year}</span>
              {/* equalizer: moves while the Bard is speaking */}
              <div className="flex h-10 items-end gap-1">
                {Array.from({ length: 7 }).map((_, i) => (
                  <motion.span
                    key={i}
                    className="w-1.5 rounded-full bg-faze"
                    animate={speaking || (started && !useBrowserVoice) ? { height: [6, 32 - (i % 3) * 7, 10, 26, 6] } : { height: 6 }}
                    transition={{ repeat: Infinity, duration: 0.9 + i * 0.07, ease: "easeInOut" }}
                  />
                ))}
              </div>
            </div>
            <div>
              {started && sentences.length > 0 ? (
                <motion.p
                  key={line}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="max-w-xl text-lg italic leading-snug text-white sm:text-xl"
                >
                  &ldquo;{sentences[Math.min(line, sentences.length - 1)]}&rdquo;
                </motion.p>
              ) : (
                <p className="display text-2xl text-white/80 sm:text-3xl">{era.label}</p>
              )}
              {current.watch_url && (
                <a
                  href={current.watch_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-3 inline-block text-xs font-bold uppercase tracking-wider text-faze hover:text-white"
                >
                  Watch {current.moments?.[0] ? `“${current.moments[0]}”` : "the moment"} on YouTube ↗
                </a>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        {!started && (
          <button className="btn btn-primary" onClick={play}>
            ▶ Play episode
          </button>
        )}
        {started && !useBrowserVoice && (
          <audio
            src={current.audio_url}
            autoPlay
            controls
            onError={() => {
              setAudioFailed(true);
              speak();
            }}
            className="h-10 w-full max-w-md"
          />
        )}
        {started && useBrowserVoice && (
          <>
            <button className="btn btn-ghost" onClick={speaking ? stop : speak}>
              {speaking ? "■ Stop" : "↻ Replay"}
            </button>
            <span className="text-xs text-muted">Narrated by the Bard</span>
          </>
        )}
      </div>

      {started && current.script && (
        <details className="mt-3 text-sm text-muted">
          <summary className="cursor-pointer text-xs uppercase tracking-widest">Read along</summary>
          <p className="mt-2 leading-relaxed">{current.script}</p>
        </details>
      )}

      {others.length > 1 && (
        <div className="mt-5 border-t border-line pt-4">
          <p className="mb-2 text-xs uppercase tracking-widest text-muted">More episodes</p>
          <div className="flex flex-wrap gap-2">
            {others.map((ep) => (
              <button
                key={ep.id}
                onClick={() => {
                  stop();
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

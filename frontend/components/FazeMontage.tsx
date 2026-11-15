"use client";
import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

/*
  "What is FaZe?" for new fans (Telemachus): a ~40 second story-style montage, from three kids posting
  trickshots in 2010 to FaZe today. Every line comes from the curated lore (backend/data/lore_seed.json).
  Auto-advances; tap/arrow keys to move, space to pause, optional narration with the browser's voice.
*/
type Slide = { years: string; kicker: string; title: string; body: string; names: string[]; accent: string };

const SLIDES: Slide[] = [
  {
    years: "2010",
    kicker: "Where it began",
    title: "Three kids. One sniper rifle.",
    body: "CLipZ, House Cat and Resistance start a YouTube channel called FaZe Sniping, posting Call of Duty trickshots.",
    names: ["CLipZ", "House Cat", "Resistance", "Fakie"],
    accent: "#e4002b",
  },
  {
    years: "2010 – 2012",
    kicker: "The trickshot years",
    title: "ILLCAMS takes over YouTube.",
    body: "The trickshot montages explode. By 2012 FaZe has a million subscribers, one of the first giant gaming channels.",
    names: ["Temperrr", "Apex", "Swan", "ILLCAMS"],
    accent: "#ff3b3b",
  },
  {
    years: "2013 – 2018",
    kicker: "The Rug era",
    title: "Gaming becomes a lifestyle.",
    body: "Rug, Banks and Adapt bring vlogs, pranks and the FaZe House. By 2018: 116 million followers and streetwear collabs.",
    names: ["Rug", "Banks", "Adapt", "The FaZe House"],
    accent: "#f5b800",
  },
  {
    years: "2016 – 2022",
    kicker: "The trophies",
    title: "FaZe wins on the biggest stages.",
    body: "Into CS:GO in 2016, Call of Duty League champions in 2021, and the first fully international roster to win a CS:GO Major in 2022.",
    names: ["CS:GO", "Atlanta FaZe", "PGL Antwerp", "Champs"],
    accent: "#e4002b",
  },
  {
    years: "2020",
    kicker: "A new generation",
    title: "Nuke Squad and #FaZe5.",
    body: "Swagg brings his Warzone squad into FaZe, and more than 211,000 people apply to join through the #FaZe5 challenge.",
    names: ["Swagg", "Santana", "Booya", "JSmooth"],
    accent: "#ff3b3b",
  },
  {
    years: "2022",
    kicker: "Mainstream",
    title: "Snoop Dogg joins FaZe.",
    body: "\"FaZe Snoop\" makes FaZe a household name far beyond gaming.",
    names: ["FaZe Snoop", "Proze", "FaZe1"],
    accent: "#f5b800",
  },
  {
    years: "2024 – 2026",
    kicker: "The road home",
    title: "The founders come back.",
    body: "Banks returns as CEO with Temperrr and Apex. FaZe rebuilds, wins the Six Invitational 2026, and starts FaZe Up Next for future stars.",
    names: ["Banks", "Temperrr", "Apex", "Up Next"],
    accent: "#e4002b",
  },
];
const SLIDE_MS = 5500;

export default function FazeMontage({
  onDone,
  onClose,
  narration,
  starting = false,
}: {
  starting?: boolean;
  onDone: () => void;
  onClose: () => void;
  narration?: (string | null)[] | null; // the Bard's clips: one per slide, then the closing line
}) {
  const [i, setI] = useState(0);
  const [paused, setPaused] = useState(false);
  const bardVoice = !!narration?.some(Boolean);
  const [voice, setVoice] = useState(bardVoice);
  const [elapsed, setElapsed] = useState(0);
  const [slideMs, setSlideMs] = useState(SLIDE_MS);
  const finished = i >= SLIDES.length;
  const last = useRef(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  useEffect(() => setVoice(bardVoice), [bardVoice]); // clips can arrive after the montage opens

  const next = useCallback(() => {
    setI((n) => Math.min(n + 1, SLIDES.length));
    setElapsed(0);
    setSlideMs(SLIDE_MS);
  }, []);
  const prev = useCallback(() => {
    setI((n) => Math.max(n - 1, 0));
    setElapsed(0);
    setSlideMs(SLIDE_MS);
  }, []);

  // progress timer
  useEffect(() => {
    if (paused || finished) return;
    last.current = performance.now();
    const id = setInterval(() => {
      const now = performance.now();
      const dt = now - last.current; // computed here: the state updater may run later
      last.current = now;
      setElapsed((e) => e + dt);
    }, 80);
    return () => clearInterval(id);
  }, [paused, finished, i]);
  useEffect(() => {
    if (!finished && elapsed >= slideMs) next();
  }, [elapsed, slideMs, next, finished]);

  // The Bard narrates: each slide lasts as long as its clip (never shorter than SLIDE_MS).
  const clip = voice && narration ? narration[Math.min(i, SLIDES.length)] : null;
  useEffect(() => {
    audioRef.current?.pause();
    audioRef.current = null;
    if (!clip) return;
    const a = new Audio(clip);
    audioRef.current = a;
    a.onloadedmetadata = () => {
      if (!finished && Number.isFinite(a.duration)) setSlideMs(Math.max(SLIDE_MS, a.duration * 1000 + 700));
    };
    a.play().catch(() => {}); // blocked autoplay: the slide just runs on its timer
    return () => a.pause();
  }, [clip, finished]);
  useEffect(() => {
    const a = audioRef.current;
    if (!a) return;
    if (paused) a.pause();
    else if (a.paused && !a.ended) a.play().catch(() => {});
  }, [paused]);

  // No Bard audio (ElevenLabs down): the voice toggle falls back to the browser voice
  useEffect(() => {
    if (!voice || bardVoice || finished || !("speechSynthesis" in window)) return;
    const s = SLIDES[i];
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(`${s.years.replace("–", "to")}. ${s.title} ${s.body}`);
    u.rate = 1.05;
    window.speechSynthesis.speak(u);
    return () => window.speechSynthesis.cancel();
  }, [i, voice, finished, bardVoice]);
  useEffect(() => () => window.speechSynthesis?.cancel(), []);

  // keyboard: arrows move, space pauses, esc closes
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") next();
      else if (e.key === "ArrowLeft") prev();
      else if (e.key === " ") {
        e.preventDefault();
        setPaused((p) => !p);
      } else if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [next, prev, onClose]);

  const s = SLIDES[Math.min(i, SLIDES.length - 1)];
  // portal to <body>: a transformed ancestor would otherwise trap "fixed" inside the page
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prevOverflow;
    };
  }, []);
  if (!mounted) return null;

  return createPortal(
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex flex-col overflow-hidden bg-black text-white"
      role="dialog"
      aria-label="What is FaZe? A short story"
    >
      {/* moving speed streaks + a glow in the slide's colour */}
      <motion.div
        className="pointer-events-none absolute inset-0 opacity-[0.08]"
        style={{ backgroundImage: "repeating-linear-gradient(-55deg, #fff 0 2px, transparent 2px 40px)" }}
        animate={{ backgroundPositionX: ["0px", "400px"] }}
        transition={{ repeat: Infinity, duration: 6, ease: "linear" }}
      />
      <motion.div
        key={`glow-${i}`}
        className="pointer-events-none absolute -right-40 -top-40 h-[36rem] w-[36rem] rounded-full blur-3xl"
        style={{ background: finished ? "#e4002b" : s.accent }}
        initial={{ opacity: 0, scale: 0.7 }}
        animate={{ opacity: 0.28, scale: 1.1 }}
        transition={{ duration: 2.5 }}
      />

      {/* story progress bars */}
      <div className="relative z-10 flex gap-1.5 px-4 pt-4 sm:px-8">
        {SLIDES.map((_, n) => (
          <div key={n} className="h-1 flex-1 overflow-hidden rounded-full bg-white/20">
            <div
              className="h-full bg-white"
              style={{ width: n < i ? "100%" : n === i ? `${Math.min(100, (elapsed / slideMs) * 100)}%` : "0%" }}
            />
          </div>
        ))}
      </div>
      <div className="relative z-10 flex items-center justify-between px-4 pt-3 text-xs font-bold uppercase tracking-[0.2em] text-white/70 sm:px-8">
        <span>FaZe in 40 seconds{bardVoice && voice ? " · narrated by the Bard" : ""}</span>
        <div className="flex items-center gap-4">
          {!finished && (
            <>
              <button onClick={() => setVoice((v) => !v)} className="hover:text-white" aria-label="Toggle narration">
                {voice ? (bardVoice ? "🔊 The Bard" : "🔊 Voice on") : "🔈 Voice off"}
              </button>
              <button onClick={() => setPaused((p) => !p)} className="hover:text-white">
                {paused ? "▶ Play" : "❚❚ Pause"}
              </button>
              <button onClick={() => setI(SLIDES.length)} className="hover:text-white">
                Skip
              </button>
            </>
          )}
          <button onClick={onClose} className="text-lg hover:text-white" aria-label="Close">
            ✕
          </button>
        </div>
      </div>

      {/* tap zones: left third back, rest forward */}
      {!finished && (
        <>
          <button className="absolute inset-y-0 left-0 z-0 w-1/3" onClick={prev} aria-label="Previous" />
          <button className="absolute inset-y-0 right-0 z-0 w-2/3" onClick={next} aria-label="Next" />
        </>
      )}

      <div className="pointer-events-none relative z-10 flex flex-1 items-center px-6 sm:px-16">
        <AnimatePresence mode="wait">
          {!finished ? (
            <motion.div key={i} className="w-full max-w-5xl" exit={{ opacity: 0, x: -40, transition: { duration: 0.25 } }}>
              <motion.p
                initial={{ opacity: 0, scale: 1.25 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.7, ease: "easeOut" }}
                className={`display select-none whitespace-nowrap leading-[0.85] ${
                  s.years.length > 4 ? "text-[clamp(3.2rem,10vw,8rem)]" : "text-[clamp(4.5rem,15vw,11rem)]"
                }`}
                style={{ color: "transparent", WebkitTextStroke: `2px ${s.accent}` }}
              >
                {s.years}
              </motion.p>
              <motion.p
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.25 }}
                className="mt-4 text-xs font-bold uppercase tracking-[0.3em]"
                style={{ color: s.accent }}
              >
                {s.kicker}
              </motion.p>
              <motion.h2
                initial={{ opacity: 0, y: 24 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.35, duration: 0.5 }}
                className="display mt-2 text-[clamp(2.2rem,6vw,4.5rem)] leading-[0.95]"
              >
                {s.title}
              </motion.h2>
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.7 }}
                className="mt-4 max-w-2xl text-lg text-white/80 sm:text-xl"
              >
                {s.body}
              </motion.p>
              <div className="mt-6 flex flex-wrap gap-2">
                {s.names.map((n, k) => (
                  <motion.span
                    key={n}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 1 + k * 0.15 }}
                    className="rounded-full border border-white/20 bg-white/5 px-3 py-1 text-xs font-semibold uppercase tracking-wider"
                  >
                    {n}
                  </motion.span>
                ))}
              </div>
            </motion.div>
          ) : (
            <motion.div key="end" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="pointer-events-auto w-full max-w-3xl">
              <p className="eyebrow">That&apos;s FaZe</p>
              <h2 className="display mt-2 text-[clamp(2.5rem,7vw,5rem)] leading-[0.95]">
                Kids who turned clips into a culture.
              </h2>
              <p className="mt-4 max-w-2xl text-lg text-white/80">
                You missed some of it. Like Telemachus searching for his father&apos;s legend, you can catch up: the Bard
                sings the story, the Siren shows you the moments, and the Oracle lets you earn your place.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <button onClick={onDone} disabled={starting} className="btn btn-primary px-8 py-3.5 text-base disabled:opacity-60">
                  {starting ? "Opening your Odyssey…" : "Start my Odyssey →"}
                </button>
                <button
                  onClick={() => {
                    setI(0);
                    setElapsed(0);
                    setSlideMs(SLIDE_MS);
                  }}
                  className="btn btn-ghost px-6 py-3.5 text-base"
                >
                  ↻ Watch again
                </button>
                <a
                  href="https://www.youtube.com/@FaZeClan"
                  target="_blank"
                  rel="noreferrer"
                  className="btn btn-ghost px-6 py-3.5 text-base"
                >
                  FaZe Clan on YouTube ↗
                </a>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      <p className="relative z-10 px-6 pb-4 text-[11px] text-white/40 sm:px-16">
        {finished ? "Facts from ITHACA's curated, sourced lore." : "Tap to skip ahead · ← → keys · space to pause"}
      </p>
    </motion.div>,
    document.body,
  );
}

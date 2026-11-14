"use client";
import { AnimatePresence, motion } from "framer-motion";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { eraById } from "@/lib/eras";
import { DEMO_FAN_ID } from "@/lib/mocks";
import type { OracleMode, OracleVerdict } from "@/lib/types";

/*
  FaceTime fallback (plan: Robustness). Same Oracle service as the Chert FaceTime agent:
  getUserMedia -> snapshot -> POST /oracle/frame -> verdict, spoken with browser TTS.
  If Chert hiccups at the judging table, open this page and keep going.
*/
function OracleCam() {
  const params = useSearchParams();
  const [mode, setMode] = useState<OracleMode>((params.get("mode") as OracleMode) === "bow_trial" ? "bow_trial" : "argos");
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [camError, setCamError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [verdict, setVerdict] = useState<OracleVerdict | null>(null);

  useEffect(() => {
    let stream: MediaStream | null = null;
    navigator.mediaDevices
      ?.getUserMedia({ video: { facingMode: "user", width: 1280, height: 720 }, audio: false })
      .then((s) => {
        stream = s;
        if (videoRef.current) videoRef.current.srcObject = s;
      })
      .catch(() => setCamError("Camera blocked. Allow camera access, or the Oracle will answer from the canned verdicts."));
    return () => stream?.getTracks().forEach((t) => t.stop());
  }, []);

  const speak = (text: string) => {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 0.92;
    u.pitch = 0.8;
    window.speechSynthesis.speak(u);
  };

  const consult = async () => {
    setBusy(true);
    setVerdict(null);
    let image = "";
    const v = videoRef.current;
    const c = canvasRef.current;
    if (v && c && v.videoWidth) {
      c.width = 640;
      c.height = Math.round((640 * v.videoHeight) / v.videoWidth);
      c.getContext("2d")?.drawImage(v, 0, 0, c.width, c.height);
      image = c.toDataURL("image/jpeg", 0.8).split(",")[1];
    }
    // api.oracleFrame times out at 6s and falls back to a canned verdict: never dead air.
    const { data } = await api.oracleFrame(DEMO_FAN_ID, mode, image);
    setVerdict(data);
    speak(data.verdict);
    setBusy(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Tiresias · The Oracle</p>
          <h1 className="font-display text-4xl font-black">Show the Oracle</h1>
          <p className="mt-2 text-muted">
            {mode === "argos"
              ? "Argos Remembers: hold up old FaZe merch, a poster or your setup."
              : "Bow Trial: play or perform a trickshot. The Oracle judges it."}
          </p>
        </div>
        <div className="flex rounded-full border border-line p-1">
          {(["argos", "bow_trial"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`rounded-full px-4 py-1.5 text-sm ${mode === m ? "bg-faze text-white" : "text-muted"}`}
            >
              {m === "argos" ? "Argos Remembers" : "Bow Trial"}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="relative overflow-hidden rounded-2xl border border-line bg-black lg:col-span-3">
          <video ref={videoRef} autoPlay playsInline muted className="aspect-video w-full -scale-x-100 object-cover" />
          {camError && <p className="absolute inset-x-0 top-1/2 px-6 text-center text-sm text-muted">{camError}</p>}
          {busy && (
            <motion.div
              className="absolute inset-0 border-4 border-gold"
              animate={{ opacity: [0.2, 1, 0.2] }}
              transition={{ repeat: Infinity, duration: 1 }}
            />
          )}
          <canvas ref={canvasRef} className="hidden" />
        </div>

        <div className="space-y-4 lg:col-span-2">
          <button className="btn btn-primary w-full py-3 text-base" onClick={consult} disabled={busy}>
            {busy ? "The Oracle sees…" : "👁 Consult the Oracle"}
          </button>
          <AnimatePresence>
            {verdict && (
              <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="card border-gold/50">
                <p className="eyebrow">The Oracle speaks</p>
                <p className="mt-3 font-display text-lg leading-relaxed text-gold-soft">&ldquo;{verdict.verdict}&rdquo;</p>
                <div className="mt-4 flex flex-wrap gap-2 text-xs">
                  {verdict.era && <span className="rounded-full bg-white/5 px-3 py-1">Era: {eraById(verdict.era).year} {eraById(verdict.era).label}</span>}
                  {verdict.confidence != null && <span className="rounded-full bg-white/5 px-3 py-1">Confidence {Math.round(verdict.confidence * 100)}%</span>}
                  {verdict.score != null && <span className="rounded-full bg-faze/20 px-3 py-1 text-faze">Score {verdict.score}</span>}
                  {verdict.drachmae_awarded && <span className="rounded-full bg-gold/15 px-3 py-1 text-gold">+{verdict.drachmae_awarded} Drachmae</span>}
                </div>
                {verdict.reasons && (
                  <ul className="mt-3 list-inside list-disc text-sm text-muted">
                    {verdict.reasons.map((r) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                )}
                {verdict.relic && <p className="mt-3 text-sm">🏺 Relic earned: <span className="font-semibold text-gold">{verdict.relic.name}</span></p>}
              </motion.div>
            )}
          </AnimatePresence>
          <p className="text-xs text-muted">Frames are processed in memory and discarded. Only the verdict and relic are stored.</p>
        </div>
      </div>
    </div>
  );
}

export default function OracleCamPage() {
  return (
    <Suspense>
      <OracleCam />
    </Suspense>
  );
}

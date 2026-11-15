"use client";
import { useConversation } from "@elevenlabs/react";
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { API_BASE, api } from "@/lib/api";

const AGENT_ID = process.env.NEXT_PUBLIC_ELEVENLABS_AGENT_ID || "";

type Line = { who: "bard" | "you"; text: string };

/*
  Arrival: voice onboarding with the Bard.
  Person B owns the ElevenLabs agent (backend/app/services/bard_agent.py). This page asks the backend for a
  session (POST /bard/agent/session: signed URL + the pre-created fan_id as a dynamic variable). The agent's
  server tool calls POST /tools/classify_fan; its client tool show_odyssey_map routes the fan to their map.
*/
export default function Onboard() {
  const router = useRouter();
  const [lines, setLines] = useState<Line[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  // Voice is available if the backend has a Bard agent (Part B) or a public agent id is baked in.
  const [voiceReady, setVoiceReady] = useState<boolean>(!!AGENT_ID);
  useEffect(() => {
    if (AGENT_ID || !API_BASE) return;
    fetch(`${API_BASE}/health`, { cache: "no-store" })
      .then((r) => r.json())
      .then((h) => setVoiceReady(!!h.bard_agent))
      .catch(() => setVoiceReady(false));
  }, []);

  const goToOdyssey = useCallback(
    (fanId: string) => setTimeout(() => router.push(`/odyssey/${encodeURIComponent(fanId)}`), 1200),
    [router],
  );

  const conversation = useConversation({
    onMessage: ({ message, source }: { message: string; source: string }) =>
      setLines((l): Line[] => [...l, { who: source === "user" ? ("you" as const) : ("bard" as const), text: message }].slice(-8)),
    onError: (e: unknown) => setError(typeof e === "string" ? e : "The Bard lost his voice. Try the typed path below."),
  });

  const start = async () => {
    setError(null);
    try {
      await navigator.mediaDevices.getUserMedia({ audio: true });
      // Part B's backend pre-creates the fan and hands back how to connect (signed URL keeps the agent private).
      const session = await api.bardSession();
      const showMap = async ({ fan_id }: { fan_id?: string }) => {
        goToOdyssey(fan_id || session?.fan_id || "demo_odysseus");
        return "Map shown to the fan.";
      };
      const connect =
        session?.mode === "signed" && session.signed_url
          ? { signedUrl: session.signed_url }
          : session?.mode === "public" && session.agent_id
            ? { agentId: session.agent_id, connectionType: "webrtc" }
            : AGENT_ID
              ? { agentId: AGENT_ID, connectionType: "webrtc" }
              : null;
      if (!connect) {
        setError("The Bard's voice isn't set up yet (no ElevenLabs agent). Use the typed path below.");
        return;
      }
      const opts = {
        ...connect,
        dynamicVariables: session?.dynamic_variables ?? {},
        // the agent (backend/app/services/bard_agent.py) calls show_odyssey_map; keep the old name too
        clientTools: { show_odyssey_map: showMap, show_odyssey: showMap },
      };
      await conversation.startSession(opts as Parameters<typeof conversation.startSession>[0]);
    } catch {
      setError("Microphone blocked or agent unreachable. Use the typed path below.");
    }
  };

  const classifyTyped = async () => {
    if (!typed.trim()) return;
    setBusy(true);
    const { data } = await api.classify(typed);
    setLines([{ who: "you", text: typed }, { who: "bard", text: data.path === "odysseus" ? "You were there. Welcome home, Odysseus." : "Then sit, Telemachus, and hear of your father's legend." }]);
    goToOdyssey(data.fan_id);
  };

  const live = conversation.status === "connected";

  return (
    <div className="mx-auto max-w-2xl space-y-8 py-6 text-center">
      <div>
        <p className="eyebrow">Arrival</p>
        <h1 className="mt-2 font-display text-4xl font-black">Speak, and the Bard will sing</h1>
        <p className="mt-3 text-muted">When did you first find FaZe? Who was your guy? What game?</p>
      </div>

      <div className="flex justify-center">
        <motion.button
          onClick={live ? () => conversation.endSession() : start}
          disabled={!voiceReady}
          animate={live && conversation.isSpeaking ? { scale: [1, 1.08, 1] } : { scale: 1 }}
          transition={{ repeat: Infinity, duration: 1.2 }}
          className={`flex h-44 w-44 flex-col items-center justify-center rounded-full border-4 text-white shadow-2xl transition disabled:cursor-not-allowed disabled:opacity-40 ${
            live ? "border-gold bg-faze shadow-faze/40" : "border-faze bg-panel hover:bg-faze/20"
          }`}
        >
          <span className="text-5xl">🎙</span>
          <span className="mt-2 text-sm font-semibold">
            {!voiceReady ? "Voice not set up yet" : live ? (conversation.isSpeaking ? "The Bard speaks…" : "Listening… tap to end") : "Tap to begin"}
          </span>
        </motion.button>
      </div>

      {lines.length > 0 && (
        <div className="card space-y-2 text-left">
          {lines.map((l, i) => (
            <motion.p key={i} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className={l.who === "bard" ? "font-display text-gold" : "text-white"}>
              <span className="mr-2 text-xs uppercase tracking-widest text-muted">{l.who === "bard" ? "Bard" : "You"}</span>
              {l.text}
            </motion.p>
          ))}
        </div>
      )}

      {error && <p className="text-sm text-faze">{error}</p>}

      <div className="card text-left">
        <p className="eyebrow">No mic? Type it</p>
        <textarea
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          rows={3}
          placeholder="I found FaZe in 2013 watching trickshot montages on MW2…"
          className="mt-3 w-full rounded-xl border border-line bg-black/40 p-3 text-sm outline-none focus:border-gold"
        />
        <button className="btn btn-primary mt-3" onClick={classifyTyped} disabled={busy}>
          {busy ? "The Bard considers…" : "Reveal my Odyssey"}
        </button>
      </div>
    </div>
  );
}

"use client";
import { useConversation } from "@elevenlabs/react";
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import { api } from "@/lib/api";

const AGENT_ID = process.env.NEXT_PUBLIC_ELEVENLABS_AGENT_ID || "";

type Line = { who: "bard" | "you"; text: string };

/*
  Arrival: voice onboarding with the Bard.
  Person B owns the ElevenLabs agent. The agent's SERVER tool calls POST /tools/classify_fan on the API.
  Ask B to also add a CLIENT tool on the agent:
    name: show_odyssey   params: { fan_id: string }
  so the Bard can say "behold your map" and this page routes the fan to it.
*/
export default function Onboard() {
  const router = useRouter();
  const [lines, setLines] = useState<Line[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);

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
      const opts = {
        agentId: AGENT_ID,
        connectionType: "webrtc",
        clientTools: {
          show_odyssey: async ({ fan_id }: { fan_id: string }) => {
            goToOdyssey(fan_id);
            return "Map shown to the fan.";
          },
        },
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
          disabled={!AGENT_ID}
          animate={live && conversation.isSpeaking ? { scale: [1, 1.08, 1] } : { scale: 1 }}
          transition={{ repeat: Infinity, duration: 1.2 }}
          className={`flex h-44 w-44 flex-col items-center justify-center rounded-full border-4 text-white shadow-2xl transition disabled:cursor-not-allowed disabled:opacity-40 ${
            live ? "border-gold bg-faze shadow-faze/40" : "border-faze bg-panel hover:bg-faze/20"
          }`}
        >
          <span className="text-5xl">🎙</span>
          <span className="mt-2 text-sm font-semibold">
            {!AGENT_ID ? "Agent not set" : live ? (conversation.isSpeaking ? "The Bard speaks…" : "Listening… tap to end") : "Tap to begin"}
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

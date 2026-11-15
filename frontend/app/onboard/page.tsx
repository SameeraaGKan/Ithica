"use client";
import { ConversationProvider, useConversation } from "@elevenlabs/react";
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE, api } from "@/lib/api";

const AGENT_ID = process.env.NEXT_PUBLIC_ELEVENLABS_AGENT_ID || "";

type Line = { who: "bard" | "you"; text: string };

/*
  Arrival: voice onboarding with the Bard.
  Person B owns the ElevenLabs agent (backend/app/services/bard_agent.py). This page asks the backend for a
  session (POST /bard/agent/session: signed URL + the pre-created fan_id as a dynamic variable). The agent's
  server tool calls POST /tools/classify_fan; its client tool show_odyssey_map routes the fan to their map.
*/
// @elevenlabs/react 1.x: useConversation must live inside a ConversationProvider.
export default function OnboardPage() {
  return (
    <ConversationProvider>
      <Onboard />
    </ConversationProvider>
  );
}

function Onboard() {
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

  const callId = useRef<string | null>(null);
  const [say, setSay] = useState("");
  const conversation = useConversation({
    // Defined explicitly: older @elevenlabs/react (0.4.x) crashed on connect when these were unset.
    onConnect: ({ conversationId }: { conversationId?: string }) => {
      setError(null);
      callId.current = conversationId ?? null;
      console.info("[ithaca] Bard call id:", conversationId);
    },
    onDisconnect: (d: unknown) => {
      console.info("[ithaca] Bard disconnected:", d);
      // Show why the call ended, so a hang-up right after the greeting isn't a mystery.
      const det = (d ?? {}) as { reason?: string; message?: string; context?: { code?: number; reason?: string } };
      if (det.reason === "user") return;
      const why =
        det.reason === "error"
          ? `connection error: ${det.message || "unknown"}`
          : `the agent ended the call${det.context?.code ? ` (code ${det.context.code})` : ""}${
              det.context?.reason ? `: ${det.context.reason}` : ""
            }`;
      setError(`The Bard hung up: ${why}. Run "python -m scripts.bard_doctor" in backend/ to see what ElevenLabs received${
        callId.current ? ` (call ${callId.current})` : ""
      }, or type to him below.`);
    },
    onDebug: (d: unknown) => console.debug("[ithaca] Bard debug:", d),
    onAudio: () => {},
    onUnhandledClientToolCall: (call: unknown) => console.warn("[ithaca] agent called an unknown client tool:", call),
    onMessage: ({ message, source }: { message: string; source: string }) =>
      setLines((l): Line[] => [...l, { who: source === "user" ? ("you" as const) : ("bard" as const), text: message }].slice(-8)),
    onError: (e: unknown) => {
      console.error("[ithaca] Bard conversation error:", e);
      setError(`The Bard lost his voice: ${typeof e === "string" ? e : e instanceof Error ? e.message : JSON.stringify(e)}. Try the typed path below.`);
    },
  });

  const start = async () => {
    setError(null);
    try {
      // Ask for mic permission, then release it right away: the ElevenLabs SDK opens its own stream, and on some
      // Windows / Bluetooth setups a second capture of the same mic receives silence while the first stays open.
      const probe = await navigator.mediaDevices.getUserMedia({ audio: true });
      probe.getTracks().forEach((t) => t.stop());
      // Part B's backend pre-creates the fan and hands back how to connect (signed URL keeps the agent private).
      const session = await api.bardSession();
      const showMap = async ({ fan_id }: { fan_id?: string }) => {
        goToOdyssey(fan_id || session?.fan_id || "demo_odysseus");
        return "Map shown to the fan.";
      };
      // The backend picks the transport: signed websocket first (WebRTC/LiveKit drops on some networks), WebRTC fallback.
      const connect =
        session?.mode === "webrtc" && session.conversation_token
          ? { conversationToken: session.conversation_token, connectionType: "webrtc" }
          : session?.mode === "signed" && session.signed_url
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
    } catch (e) {
      console.error("[ithaca] Bard voice failed to start:", e);
      const msg = e instanceof Error ? e.message : String(e);
      const micBlocked = /permission|notallowed|denied|not found|device/i.test(msg);
      setError(
        micBlocked
          ? `Microphone blocked (${msg}). Click the lock icon in the address bar, allow the microphone, and reload.`
          : `The Bard couldn't connect: ${msg}. Use the typed path below.`,
      );
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

  // Live readout while connected: is the mic reaching the SDK, and whose turn is it?
  const [micLevel, setMicLevel] = useState(0);
  const [peak, setPeak] = useState(0);
  useEffect(() => {
    if (!live) {
      setMicLevel(0);
      return;
    }
    const id = setInterval(() => {
      const v = conversation.getInputVolume?.() ?? 0;
      setMicLevel(v);
      setPeak((p) => Math.max(p, v));
    }, 120);
    return () => clearInterval(id);
  }, [live, conversation]);
  const heardYou = lines.some((l) => l.who === "you");
  const sendSay = () => {
    const t = say.trim();
    if (!t) return;
    conversation.sendUserMessage(t);
    setLines((l): Line[] => [...l, { who: "you" as const, text: t }].slice(-8));
    setSay("");
  };

  return (
    <div className="mx-auto max-w-2xl space-y-8 py-6 text-center">
      <div className="hero-band">
        <p className="eyebrow">Arrival</p>
        <h1 className="display mt-2 text-5xl">Speak, and the Bard will sing</h1>
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

      {live && (
        <div className="card space-y-2 text-left text-sm">
          <div className="flex items-center justify-between">
            <span className="text-muted">Your mic</span>
            <span className="text-muted">{conversation.isSpeaking ? "The Bard is speaking" : "The Bard is listening"}</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-white/10">
            <div className="h-full rounded-full bg-gold transition-all" style={{ width: `${Math.min(100, micLevel * 250)}%` }} />
          </div>
          <p className="text-xs text-muted">
            {peak < 0.02
              ? "No sound from your mic yet. Speak up, or pick the right microphone in Chrome (lock icon → Site settings)."
              : heardYou
                ? "The Bard hears you."
                : "Your mic works. If no 'You' line appears after you speak, type your answer here instead."}
          </p>
          <div className="flex gap-2 pt-1">
            <input
              value={say}
              onChange={(e) => setSay(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendSay()}
              placeholder="Or type to the Bard… (e.g. 2013, Clayster, MW2)"
              className="flex-1 rounded-xl border border-line bg-black/40 px-3 py-2 text-sm outline-none focus:border-gold"
            />
            <button className="btn btn-primary" onClick={sendSay}>Send</button>
          </div>
        </div>
      )}

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

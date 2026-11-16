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
  Default (BARD_VOICE=free): the browser listens and speaks, POST /bard/chat writes his lines, no ElevenLabs credits.
  With BARD_VOICE=elevenlabs on the backend, the ElevenLabs agent below runs the call instead:
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
  const [busy, setBusy] = useState(false);
  // Voice is available if the backend has a Bard agent (Part B) or a public agent id is baked in.
  const [voiceReady, setVoiceReady] = useState<boolean>(!!AGENT_ID);
  useEffect(() => {
    if (AGENT_ID || !API_BASE) return;
    fetch(`${API_BASE}/health`, { cache: "no-store" })
      .then((r) => r.json())
      .then((h) => setVoiceReady(h.bard_voice === "free" || !!h.bard_agent))
      .catch(() => setVoiceReady(false));
  }, []);

  const goToOdyssey = useCallback(
    (fanId: string) => setTimeout(() => router.push(`/odyssey/${encodeURIComponent(fanId)}`), 1200),
    [router],
  );

  const callId = useRef<string | null>(null);
  const sessionFan = useRef<string | null>(null);
  const sentHome = useRef(false);
  const heardFan = useRef(false); // the fan has answered at least once (voice or typed)
  // The agent should call show_odyssey_map, but sometimes only says goodbye: open the map ourselves then.
  const sendHome = useCallback(() => {
    if (sentHome.current) return;
    sentHome.current = true;
    goToOdyssey(sessionFan.current || "demo_odysseus");
  }, [goToOdyssey]);
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
      if (det.reason === "agent" && heardFan.current) return sendHome(); // the Bard finished and hung up
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
    onMessage: ({ message, source }: { message: string; source: string }) => {
      const text = message.replace(/\[[a-z ]{2,20}\]\s*/gi, "").trim(); // expressive voice tags like [warm]
      if (source === "user") heardFan.current = true;
      // farewell with the map (voice or typed answers, same path): reveal the Odyssey once he's said it
      else if (heardFan.current && /odyssey map|look upon your odyssey/i.test(text)) setTimeout(sendHome, 4000);
      setLines((l): Line[] => [...l, { who: source === "user" ? ("you" as const) : ("bard" as const), text }].slice(-8));
    },
    onError: (e: unknown) => {
      console.error("[ithaca] Bard conversation error:", e);
      setError(`The Bard lost his voice: ${typeof e === "string" ? e : e instanceof Error ? e.message : JSON.stringify(e)}. Try the typed path below.`);
    },
  });

  // ---- The free Bard: the browser listens (Web Speech API), /bard/chat answers, the browser speaks. No credits.
  const [freeLive, setFreeLive] = useState(false);
  const [freeSpeaking, setFreeSpeaking] = useState(false);
  const freeOn = useRef(false);
  const turnBusy = useRef(false);
  const micDenied = useRef(false); // mic blocked: keep chatting by typing
  const rec = useRef<{ abort: () => void } | null>(null);
  const hist = useRef<Line[]>([]);
  const addLine = (l: Line) => {
    hist.current = [...hist.current, l];
    setLines(hist.current.slice(-8));
  };
  const speak = (text: string) =>
    new Promise<void>((resolve) => {
      if (!("speechSynthesis" in window)) return resolve();
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      const voices = window.speechSynthesis.getVoices();
      // a deeper English storyteller voice when the browser has one
      u.voice = voices.find((v) => /^en/i.test(v.lang) && /daniel|george|ryan|guy|male/i.test(v.name)) || voices.find((v) => /^en/i.test(v.lang)) || null;
      u.rate = 0.95;
      u.pitch = 0.9;
      u.onend = u.onerror = () => resolve();
      setTimeout(resolve, 2500 + text.length * 90); // some browsers never fire onend: never freeze the chat
      setFreeSpeaking(true);
      window.speechSynthesis.speak(u);
    }).finally(() => setFreeSpeaking(false));
  const stopFree = () => {
    freeOn.current = false;
    setFreeLive(false);
    rec.current?.abort();
    rec.current = null;
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  };
  useEffect(() => stopFree, []); // leaving the page stops listening and speaking
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const SR = typeof window !== "undefined" ? ((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition) : null;
  const listen = () => {
    if (!freeOn.current || !SR || micDenied.current || turnBusy.current || rec.current) return;
    const r = new SR();
    r.lang = "en-US";
    r.interimResults = false;
    r.maxAlternatives = 1;
    r.onresult = (e: { results: { [i: number]: { [j: number]: { transcript: string } } } }) => {
      const t = e.results[0][0].transcript.trim();
      if (t) freeTurn(t);
    };
    r.onerror = (e: { error: string }) => {
      if (e.error === "not-allowed") {
        micDenied.current = true;
        setError("Microphone blocked. Allow it from the lock icon in the address bar, or type to the Bard below.");
      }
    };
    r.onend = () => {
      if (rec.current === r) rec.current = null;
      listen(); // silence ends a listen: keep listening until the fan speaks or the chat ends
    };
    rec.current = r;
    r.start();
  };
  const freeTurn = async (text: string) => {
    heardFan.current = true;
    turnBusy.current = true;
    rec.current?.abort();
    rec.current = null;
    addLine({ who: "you", text });
    const r = await api.bardChat(sessionFan.current, hist.current);
    const reply = r?.reply ?? "The songs are quiet for a moment, traveler. Tell me again?";
    if (r?.fan_id) sessionFan.current = r.fan_id;
    addLine({ who: "bard", text: reply });
    await speak(reply);
    turnBusy.current = false;
    if (r?.done) {
      stopFree();
      sendHome();
    } else listen();
  };
  const startFree = async () => {
    freeOn.current = true;
    micDenied.current = false;
    setFreeLive(true);
    hist.current = [];
    setLines([]);
    if (!SR) setError("Voice input needs Chrome or Edge. Type to the Bard below, he'll still answer out loud.");
    turnBusy.current = true;
    const first = await api.bardChat(sessionFan.current, []);
    const line = first?.reply ?? "Sing to me, traveler. Tell me: when did you first find FaZe?";
    addLine({ who: "bard", text: line });
    await speak(line);
    turnBusy.current = false;
    listen();
  };

  const start = async () => {
    setError(null);
    try {
      // Part B's backend pre-creates the fan and hands back how to connect (signed URL keeps the agent private).
      const session = await api.bardSession();
      sessionFan.current = session?.fan_id ?? null;
      sentHome.current = false;
      heardFan.current = false;
      if (session?.mode === "free" || (!session && !AGENT_ID)) return startFree();
      // Ask for mic permission, then release it right away: the ElevenLabs SDK opens its own stream, and on some
      // Windows / Bluetooth setups a second capture of the same mic receives silence while the first stays open.
      const probe = await navigator.mediaDevices.getUserMedia({ audio: true });
      probe.getTracks().forEach((t) => t.stop());
      const showMap = async ({ fan_id }: { fan_id?: string }) => {
        if (fan_id) sessionFan.current = fan_id;
        setTimeout(sendHome, 6000); // let him finish the farewell line first
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

  // "Show my Odyssey": classify everything the fan has told the Bard so far (voice or typed), same as the typed path.
  const revealFromChat = async () => {
    const said = lines.filter((l) => l.who === "you").map((l) => l.text).join(" ");
    if (!said.trim()) return;
    setBusy(true);
    sentHome.current = true; // no second jump from the farewell timer
    stopFree();
    const { data } = await api.classify(said, sessionFan.current);
    if (conversation.status === "connected") await conversation.endSession();
    goToOdyssey(data.fan_id);
  };

  const agentLive = conversation.status === "connected"; // ElevenLabs call
  const live = agentLive || freeLive;
  const speaking = agentLive ? conversation.isSpeaking : freeSpeaking;

  // Live readout while connected: is the mic reaching the SDK, and whose turn is it?
  const [micLevel, setMicLevel] = useState(0);
  useEffect(() => {
    if (!agentLive) {
      setMicLevel(0);
      return;
    }
    const id = setInterval(() => {
      const v = conversation.getInputVolume?.() ?? 0;
      setMicLevel(v);
    }, 120);
    return () => clearInterval(id);
  }, [agentLive, conversation]);
  const heardYou = lines.some((l) => l.who === "you");
  const sendSay = () => {
    const t = say.trim();
    if (!t) return;
    setSay("");
    if (freeLive) return void freeTurn(t); // the free Bard answers typed lines out loud too
    if (agentLive) conversation.sendUserMessage(t); // no call running: it's kept for "Show my Odyssey"
    else heardFan.current = true;
    setLines((l): Line[] => [...l, { who: "you" as const, text: t }].slice(-8));
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
          onClick={freeLive ? stopFree : agentLive ? () => conversation.endSession() : start}
          disabled={!voiceReady}
          animate={live && speaking ? { scale: [1, 1.08, 1] } : { scale: 1 }}
          transition={{ repeat: Infinity, duration: 1.2 }}
          className={`flex h-44 w-44 flex-col items-center justify-center rounded-full border-4 text-white shadow-2xl transition disabled:cursor-not-allowed disabled:opacity-40 ${
            live ? "border-gold bg-faze shadow-faze/40" : "border-faze bg-panel hover:bg-faze/20"
          }`}
        >
          <span className="text-5xl">🎙</span>
          <span className="mt-2 text-sm font-semibold">
            {!voiceReady ? "Voice not set up yet" : live ? (speaking ? "The Bard speaks…" : "Listening… tap to end") : "Tap to begin"}
          </span>
        </motion.button>
      </div>

      {/* One box: the conversation, one input (voice or typed both land here), one button to reveal the Odyssey */}
      <div className="card space-y-3 text-left">
        {agentLive && (
          <div className="h-1 w-full overflow-hidden rounded-full bg-white/10" aria-label="Your mic level">
            <div className="h-full rounded-full bg-gold transition-all" style={{ width: `${Math.min(100, micLevel * 250)}%` }} />
          </div>
        )}
        {lines.map((l, i) => (
          <motion.p key={i} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className={l.who === "bard" ? "font-display text-gold" : "text-white"}>
            <span className="mr-2 text-xs uppercase tracking-widest text-muted">{l.who === "bard" ? "Bard" : "You"}</span>
            {l.text}
          </motion.p>
        ))}
        <div className="flex gap-2">
          <input
            value={say}
            onChange={(e) => setSay(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendSay()}
            placeholder={live ? "Speak, or type to the Bard…" : "When did you find FaZe? Who was your guy? What game?"}
            className="flex-1 rounded-xl border border-line bg-black/40 px-3 py-2 text-sm outline-none focus:border-gold"
          />
          <button className="btn btn-primary" onClick={sendSay}>Send</button>
        </div>
        {heardYou && (
          <button onClick={revealFromChat} disabled={busy} className="btn btn-primary w-full disabled:opacity-60">
            {busy ? "Opening your Odyssey…" : "Show my Odyssey →"}
          </button>
        )}
        {error && <p className="text-sm text-faze">{error}</p>}
      </div>
    </div>
  );
}

"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Omen = { omen_id: string; question: string; reward: number };

// P1 Daily Omen: today's lore question. The same answer rules apply as over iMessage.
export default function DailyOmen({ fanId }: { fanId: string }) {
  const [omen, setOmen] = useState<Omen | null>(null);
  const [answer, setAnswer] = useState("");
  const [reply, setReply] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.omen().then((r) => setOmen(r.data));
  }, []);

  if (!omen) return null;

  const submit = async () => {
    if (!answer.trim()) return;
    setBusy(true);
    const { data } = await api.omenAnswer(fanId, answer);
    setReply(data.reply);
    setBusy(false);
  };

  return (
    <div className="card">
      <p className="eyebrow">Daily Omen · +{omen.reward} Drachmae</p>
      <p className="mt-2 text-sm text-white">{omen.question}</p>
      {reply ? (
        <p className="mt-3 text-sm text-gold">{reply}</p>
      ) : (
        <div className="mt-3 flex gap-2">
          <input
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            placeholder="Your answer"
            className="min-w-0 flex-1 rounded-md border border-line bg-black/40 px-3 py-2 text-sm outline-none focus:border-faze"
          />
          <button className="btn btn-primary" onClick={submit} disabled={busy}>
            Answer
          </button>
        </div>
      )}
    </div>
  );
}

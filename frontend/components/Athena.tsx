"use client";
import { AnimatePresence, motion } from "framer-motion";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { DEMO_FAN_ID } from "@/lib/mocks";
import type { Quest } from "@/lib/types";

/*
  Athena: in the Odyssey she guides Odysseus home and walks Telemachus through his search.
  Here she floats on every page, shows the fan's next step and ticks steps off as they happen
  (the backend works out progress from real events: Siren collects, Oracle verdicts, trials, claims).
*/

// The fan Athena follows: whoever's Odyssey was opened last, else the demo fan.
export const FAN_KEY = "ithaca_fan";
export function rememberFan(fanId: string) {
  try {
    localStorage.setItem(FAN_KEY, fanId);
  } catch {}
}
function currentFan(): string {
  try {
    return localStorage.getItem(FAN_KEY) || DEMO_FAN_ID;
  } catch {
    return DEMO_FAN_ID;
  }
}

// What Athena says on pages that aren't a quest step.
const PAGE_TIPS: Record<string, string> = {
  "/warroom": "This is FaZe's war room: how Ithaca brings fans home and how it earns.",
  "/tiers": "Every relic raises you. Claim what you've unlocked, and the Pass opens the meet & greet.",
};

export default function Athena() {
  const path = usePathname() || "/";
  const [quest, setQuest] = useState<Quest | null>(null);
  const [open, setOpen] = useState(true);
  const [list, setList] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = () => api.quest(currentFan()).then((r) => alive && setQuest(r.data));
    load();
    const id = setInterval(load, 3000); // Siren collects happen in another tab: keep up
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [path]);

  // The home page has its own two buttons; the onboarding page is step 1 itself.
  if (path === "/" || path.startsWith("/onboard") || !quest) return null;

  const step = quest.current;
  const tip = PAGE_TIPS[path];
  const onStepPage = step && path === step.href.split(/[?#]/)[0];

  return (
    <div className="fixed bottom-4 right-4 z-40 w-[min(92vw,340px)]">
      <AnimatePresence mode="wait">
        {open ? (
          <motion.div
            key="card"
            initial={{ opacity: 0, y: 16, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.96 }}
            className="overflow-hidden rounded-2xl border border-gold/50 bg-ink/95 shadow-2xl shadow-black/60 backdrop-blur"
          >
            <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
              <div className="flex items-center gap-2">
                <span className="text-xl">🦉</span>
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.2em] text-gold">Athena</p>
                  <p className="text-[11px] text-muted">
                    Quest {Math.min(quest.completed + 1, quest.total)} of {quest.total}
                  </p>
                </div>
              </div>
              <button onClick={() => setOpen(false)} className="text-lg text-muted hover:text-white" aria-label="Hide Athena">
                –
              </button>
            </div>

            <div className="h-1 w-full bg-white/10">
              <motion.div
                className="h-full bg-gold"
                animate={{ width: `${(quest.completed / quest.total) * 100}%` }}
                transition={{ duration: 0.6 }}
              />
            </div>

            <div className="space-y-3 p-4">
              {step ? (
                <>
                  <p className="display text-xl">{step.title}</p>
                  <p className="text-sm italic leading-snug text-gold-soft">&ldquo;{tip && !onStepPage ? tip : step.line}&rdquo;</p>
                  <Link href={step.href} className="btn btn-gold w-full">
                    {step.cta} →
                  </Link>
                  <button
                    onClick={async () => {
                      const r = await api.questMark(quest.fan_id, step.key);
                      if (r.data) setQuest(r.data);
                    }}
                    className="w-full text-center text-xs font-bold uppercase tracking-wider text-muted transition hover:text-white"
                  >
                    Done, next step →
                  </button>
                </>
              ) : (
                <>
                  <p className="display text-xl">Your Odyssey is complete</p>
                  <p className="text-sm italic text-gold-soft">&ldquo;You came home, and Ithaca knows your name. Share your recap, traveler.&rdquo;</p>
                  <Link href={`/odyssey/${quest.fan_id}`} className="btn btn-gold w-full">
                    See my Odyssey →
                  </Link>
                </>
              )}

              <button onClick={() => setList((v) => !v)} className="w-full text-left text-[11px] uppercase tracking-widest text-muted hover:text-white">
                {list ? "▾" : "▸"} The journey
              </button>
              {list && (
                <ol className="space-y-1.5">
                  {quest.steps.map((s, i) => (
                    <li key={s.key}>
                      <Link href={s.href} className="flex items-center gap-2 rounded px-1 py-0.5 text-xs transition hover:bg-white/5">
                      <span
                        className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${
                          s.done ? "bg-gold text-ink" : s.key === step?.key ? "bg-faze text-white" : "bg-white/10 text-muted"
                        }`}
                      >
                        {s.done ? "✓" : i + 1}
                      </span>
                      <span className={s.done ? "text-muted line-through" : s.key === step?.key ? "text-white" : "text-muted"}>
                        {s.title}
                      </span>
                      </Link>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          </motion.div>
        ) : (
          <motion.button
            key="pill"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            onClick={() => setOpen(true)}
            className="ml-auto flex items-center gap-2 rounded-full border border-gold/60 bg-ink/95 px-4 py-2 text-sm shadow-xl"
          >
            <span>🦉</span>
            <span className="font-bold text-gold">
              {quest.completed}/{quest.total}
            </span>
            <span className="text-muted">{step ? step.title : "Complete"}</span>
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  );
}

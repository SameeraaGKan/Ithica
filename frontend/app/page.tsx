"use client";
import Link from "next/link";
import { motion } from "framer-motion";
import { DEMO_FAN_ID } from "@/lib/mocks";

const PILLARS = [
  { num: "01", title: "The Bard", odyssey: "Demodocus", body: "Talk for 60 seconds. The Bard sings your FaZe history back to you." },
  { num: "02", title: "The Oracle", odyssey: "Tiresias", body: "FaceTime it. Show your old merch or a trickshot. It sees, and it judges." },
  { num: "03", title: "The Siren", odyssey: "The Sirens' song", body: "Every FaZe video on YouTube and Twitch, now with lore and relics." },
];

export default function Landing() {
  return (
    <div className="space-y-12">
      <section className="relative overflow-hidden rounded-3xl border border-line bg-ink px-6 py-16 sm:px-12 sm:py-24">
        {/* Speed streaks behind the headline */}
        <div className="pointer-events-none absolute inset-0 opacity-[0.07]" style={{ backgroundImage: "repeating-linear-gradient(-55deg, #fff 0 2px, transparent 2px 36px)" }} />
        <div className="pointer-events-none absolute -right-24 -top-24 h-80 w-80 rounded-full bg-faze/30 blur-3xl" />

        <motion.p initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} className="eyebrow relative">
          ◉ Every fan&apos;s road home
        </motion.p>
        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15, duration: 0.6 }}
          className="display relative mt-4 text-[clamp(4rem,14vw,9rem)] leading-[0.9]"
        >
          <span className="text-faze">I</span>THACA
        </motion.h1>
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="relative mt-6 max-w-xl text-lg text-muted"
        >
          Odysseus came home after twenty years. So can you. Grew up on trickshots, or just found FaZe?
          The Bard will find your place in the story.
        </motion.p>
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8 }}
          className="relative mt-10 flex flex-wrap gap-3"
        >
          <Link href="/onboard" className="btn btn-primary px-8 py-3.5 text-base">
            🎙 Talk to the Bard
          </Link>
          <Link href={`/odyssey/${DEMO_FAN_ID}`} className="btn btn-ghost px-8 py-3.5 text-base">
            Enter as demo fan
          </Link>
        </motion.div>
        <div className="meander absolute inset-x-0 bottom-0" />
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        {PILLARS.map((p, i) => (
          <motion.div
            key={p.title}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.1 }}
            className="card"
          >
            <span className="display absolute right-4 top-2 text-7xl text-white/5">{p.num}</span>
            <p className="eyebrow">{p.odyssey}</p>
            <h3 className="display mt-2 text-3xl">{p.title}</h3>
            <p className="mt-2 text-sm text-muted">{p.body}</p>
          </motion.div>
        ))}
      </section>

      <section className="grid gap-4 sm:grid-cols-2">
        <div className="card">
          <p className="eyebrow">Odysseus</p>
          <h3 className="display mt-2 text-2xl">Returning fan</h3>
          <p className="mt-2 text-sm text-muted">You were there. The Bard remembers your era and brings you home.</p>
        </div>
        <div className="card">
          <p className="eyebrow">Telemachus</p>
          <h3 className="display mt-2 text-2xl">New fan</h3>
          <p className="mt-2 text-sm text-muted">You found FaZe late. Here is the legend you missed, and why the name matters.</p>
        </div>
      </section>
    </div>
  );
}

"use client";
import Link from "next/link";
import { motion } from "framer-motion";
import { DEMO_FAN_ID } from "@/lib/mocks";

const PILLARS = [
  { title: "The Bard", odyssey: "Demodocus", body: "Talk for 60 seconds. The Bard sings your FaZe history back to you." },
  { title: "The Oracle", odyssey: "Tiresias", body: "FaceTime it. Show your old merch or a trickshot. It sees, and it judges." },
  { title: "The Siren", odyssey: "The Sirens' song", body: "Every FaZe video on YouTube and Twitch, now with lore and relics." },
];

export default function Landing() {
  return (
    <div className="space-y-16">
      <section className="relative overflow-hidden rounded-3xl border border-line bg-gradient-to-b from-faze-dark/40 via-panel to-ink px-6 py-20 text-center sm:px-12">
        <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="eyebrow">
          Every fan&apos;s road home
        </motion.p>
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15, duration: 0.7 }}
          className="mt-4 font-display text-5xl font-black tracking-wider sm:text-7xl"
        >
          <span className="text-faze">I</span>THACA
        </motion.h1>
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="mx-auto mt-5 max-w-xl text-lg text-muted"
        >
          Odysseus came home after twenty years. So can you. Grew up on trickshots, or just found FaZe?
          The Bard will find your place in the story.
        </motion.p>
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8 }}
          className="mt-10 flex flex-wrap justify-center gap-3"
        >
          <Link href="/onboard" className="btn btn-primary px-8 py-3 text-base">
            🎙 Talk to the Bard
          </Link>
          <Link href={`/odyssey/${DEMO_FAN_ID}`} className="btn btn-ghost px-8 py-3 text-base">
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
            <p className="eyebrow">{p.odyssey}</p>
            <h3 className="mt-2 font-display text-2xl font-bold">{p.title}</h3>
            <p className="mt-2 text-sm text-muted">{p.body}</p>
          </motion.div>
        ))}
      </section>

      <section className="grid gap-4 sm:grid-cols-2">
        <div className="card border-gold/30">
          <p className="eyebrow">Odysseus</p>
          <h3 className="mt-2 font-display text-xl font-bold">Returning fan</h3>
          <p className="mt-2 text-sm text-muted">You were there. The Bard remembers your era and brings you home.</p>
        </div>
        <div className="card border-gold/30">
          <p className="eyebrow">Telemachus</p>
          <h3 className="mt-2 font-display text-xl font-bold">New fan</h3>
          <p className="mt-2 text-sm text-muted">You found FaZe late. Here is the legend you missed, and why the name matters.</p>
        </div>
      </section>
    </div>
  );
}

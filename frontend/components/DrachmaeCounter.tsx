"use client";
import { animate, motion, useMotionValue, useTransform } from "framer-motion";
import { useEffect, useRef, useState } from "react";

// Animated count-up. When the Siren extension collects a relic, the poll picks up the
// new total and this ticks up with a +N flash — the beat from pitch step 5.
export default function DrachmaeCounter({ value }: { value: number }) {
  const mv = useMotionValue(value);
  const rounded = useTransform(mv, (v) => Math.round(v).toLocaleString());
  const prev = useRef(value);
  const [gain, setGain] = useState<number | null>(null);

  useEffect(() => {
    const diff = value - prev.current;
    prev.current = value;
    const controls = animate(mv, value, { duration: 1.2, ease: "easeOut" });
    if (diff > 0) {
      setGain(diff);
      const t = setTimeout(() => setGain(null), 1800);
      return () => {
        controls.stop();
        clearTimeout(t);
      };
    }
    return () => controls.stop();
  }, [value, mv]);

  return (
    <div className="relative flex items-center gap-2 rounded-full border border-gold/40 bg-gold/10 px-4 py-2">
      <span className="text-lg">🪙</span>
      <motion.span className="display text-2xl text-gold">{rounded}</motion.span>
      <span className="text-xs uppercase tracking-widest text-gold/70">Drachmae</span>
      {gain && (
        <motion.span
          key={value}
          initial={{ opacity: 1, y: 0 }}
          animate={{ opacity: 0, y: -28 }}
          transition={{ duration: 1.6 }}
          className="absolute -top-2 right-3 font-bold text-gold"
        >
          +{gain}
        </motion.span>
      )}
    </div>
  );
}

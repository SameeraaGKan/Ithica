"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { currentFan } from "@/components/Athena";
import { DEMO_FAN_ID } from "@/lib/mocks";

const LINKS = [
  { href: "/", label: "Home", match: "/" },
  { href: "/odyssey", label: "My Odyssey", match: "/odyssey" }, // the fan id is filled in below
  { href: "/oracle-cam", label: "Oracle", match: "/oracle-cam" },
  { href: "/tiers", label: "Tiers", match: "/tiers" },
  { href: "/warroom", label: "War Room", match: "/warroom" },
];

export default function Nav() {
  const path = usePathname();
  // "My Odyssey" opens the fan you onboarded as (read after mount: localStorage), not always the demo fan
  const [fan, setFan] = useState(DEMO_FAN_ID);
  useEffect(() => setFan(currentFan()), [path]);
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-ink/90 backdrop-blur">
      <div className="h-1 bg-faze" />
      <nav className="mx-auto flex max-w-6xl items-center gap-4 overflow-x-auto px-4 py-3 sm:px-6">
        <Link href="/" className="display shrink-0 text-2xl">
          <span className="text-faze">I</span>THACA
        </Link>
        <div className="ml-auto flex gap-1">
          {LINKS.map((l) => {
            const active = l.match === "/" ? path === "/" : path?.startsWith(l.match);
            return (
              <Link
                key={l.href}
                href={l.match === "/odyssey" ? `/odyssey/${encodeURIComponent(fan)}` : l.href}
                aria-label={l.label}
                className={`shrink-0 rounded-md px-3 py-1.5 text-xs font-bold uppercase tracking-wider transition ${
                  active ? "bg-faze text-white" : "text-muted hover:text-white"
                }`}
              >
                {l.match === "/" ? (
                  <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor" aria-hidden="true">
                    <path d="M12 3 2 12h3v9h6v-6h2v6h6v-9h3z" />
                  </svg>
                ) : (
                  l.label
                )}
              </Link>
            );
          })}
        </div>
      </nav>
    </header>
  );
}

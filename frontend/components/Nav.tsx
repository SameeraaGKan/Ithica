"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { DEMO_FAN_ID } from "@/lib/mocks";

const LINKS = [
  { href: `/odyssey/${DEMO_FAN_ID}`, label: "My Odyssey", match: "/odyssey" },
  { href: "/leaderboard", label: "Suitors", match: "/leaderboard" },
  { href: "/oracle-cam", label: "Oracle", match: "/oracle-cam" },
  { href: "/pass", label: "Pass", match: "/pass" },
  { href: "/warroom", label: "War Room", match: "/warroom" },
];

export default function Nav() {
  const path = usePathname();
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-ink/85 backdrop-blur">
      <nav className="mx-auto flex max-w-6xl items-center gap-4 overflow-x-auto px-4 py-3 sm:px-6">
        <Link href="/" className="shrink-0 font-display text-xl font-black tracking-widest">
          <span className="text-faze">I</span>THACA
        </Link>
        <div className="ml-auto flex gap-1">
          {LINKS.map((l) => {
            const active = path?.startsWith(l.match);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`shrink-0 rounded-full px-3 py-1.5 text-sm transition ${
                  active ? "bg-faze text-white" : "text-muted hover:text-white"
                }`}
              >
                {l.label}
              </Link>
            );
          })}
        </div>
      </nav>
    </header>
  );
}

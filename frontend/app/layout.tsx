import type { Metadata } from "next";
import { Cinzel, Inter } from "next/font/google";
import Nav from "@/components/Nav";
import "./globals.css";

const cinzel = Cinzel({ subsets: ["latin"], variable: "--font-cinzel", weight: ["500", "700", "900"] });
const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "ITHACA — the road home to FaZe",
  description: "A voice-first lore and trials platform that brings every FaZe fan home.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${cinzel.variable} ${inter.variable}`} suppressHydrationWarning>
      <body className="min-h-screen font-sans antialiased" suppressHydrationWarning>
        <Nav />
        <main className="mx-auto w-full max-w-6xl px-4 pb-20 pt-6 sm:px-6">{children}</main>
      </body>
    </html>
  );
}

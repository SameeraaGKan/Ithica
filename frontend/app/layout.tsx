import type { Metadata } from "next";
import { Anton, Inter } from "next/font/google";
import Nav from "@/components/Nav";
import "./globals.css";

const anton = Anton({ subsets: ["latin"], variable: "--font-anton", weight: "400" });
const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "ITHACA — the road home to FaZe",
  description: "A voice-first lore and trials platform that brings every FaZe fan home.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${anton.variable} ${inter.variable}`} suppressHydrationWarning>
      <body className="min-h-screen font-sans antialiased" suppressHydrationWarning>
        <Nav />
        <main className="mx-auto w-full max-w-6xl px-4 pb-20 pt-6 sm:px-6">{children}</main>
      </body>
    </html>
  );
}

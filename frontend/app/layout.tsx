import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CareerHarness — Standalone AI Career Agent Platform",
  description: "Next-generation career agent platform with BYOK economics and deep agent loop orchestration.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#0b0f17] text-slate-100 min-h-screen flex flex-col">
        {children}
      </body>
    </html>
  );
}

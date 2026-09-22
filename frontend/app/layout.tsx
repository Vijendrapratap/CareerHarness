import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CareerHarness — AI Career Agent Platform",
  description: "Candidate career journey with AI harness and light neumorphism.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-wash text-ink min-h-screen">{children}</body>
    </html>
  );
}

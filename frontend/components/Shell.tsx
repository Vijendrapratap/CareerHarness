"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  ["Counsel", "/counsel", "🧭"],
  ["To-dos", "/todos", "⚡"],
  ["Mailbox", "/mailbox", "📬"],
  ["Jobs", "/jobs", "🎯"],
  ["Applications", "/applications", "📋"],
  ["Inbox", "/inbox", "💬"],
  ["Calendar", "/calendar", "📅"],
  ["Settings", "/settings", "⚙️"],
];

export function Shell({ title, children }: { title: string; children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="mx-auto max-w-7xl w-full px-4 sm:px-6 lg:px-8 py-4 sm:py-6">
      <header className="neo-raised mb-6 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 px-4 sm:px-6 py-4 border border-white/80 bg-white/70 backdrop-blur-md shadow-lg shadow-slate-300/30">
        <div className="flex items-center gap-3">
          <div className="h-11 w-11 rounded-2xl bg-gradient-to-tr from-teal-700 via-emerald-600 to-sky-500 flex items-center justify-center text-white font-black text-lg shadow-md shadow-teal-700/25 border border-teal-300/40 shrink-0">
            CH
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs uppercase tracking-wider font-bold text-teal-900">CareerHarness</span>
              <span className="badge-sky text-[10px] py-0.5 px-2 font-semibold">DeepSeek v4.1</span>
              <span className="badge-emerald text-[10px] py-0.5 px-2 font-semibold hidden sm:inline-flex">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Live Agent
              </span>
            </div>
            <h1 className="text-lg sm:text-xl font-bold text-ink tracking-tight">{title}</h1>
          </div>
        </div>
        <nav className="flex items-center gap-1.5 overflow-x-auto max-w-full pb-1 lg:pb-0 scrollbar-thin">
          {links.map(([label, href, icon]) => {
            const isActive = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={`px-3 py-2 text-xs font-semibold rounded-xl transition-all duration-150 flex items-center gap-1.5 shrink-0 min-h-[40px] touch-manipulation ${
                  isActive
                    ? "neo-pressed text-teal-950 font-bold shadow-inner border border-teal-500/50 bg-gradient-to-r from-teal-50/80 via-emerald-50/50 to-cyan-50/40"
                    : "neo-raised text-muted hover:text-teal-800 hover:border-teal-300/50 hover:-translate-y-0.5"
                }`}
              >
                <span className="text-xs">{icon}</span>
                <span>{label}</span>
                {isActive && (
                  <span className="h-1.5 w-1.5 rounded-full bg-teal-600 animate-pulse ml-0.5" />
                )}
              </Link>
            );
          })}
        </nav>
      </header>
      <main className="w-full">{children}</main>
    </div>
  );
}

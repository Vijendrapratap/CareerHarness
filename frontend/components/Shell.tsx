"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  ["Counsel", "/counsel"],
  ["To-dos", "/todos"],
  ["Mailbox", "/mailbox"],
  ["Jobs", "/jobs"],
  ["Applications", "/applications"],
  ["Inbox", "/inbox"],
  ["Calendar", "/calendar"],
  ["Settings", "/settings"],
];

export function Shell({ title, children }: { title: string; children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <header className="neo-raised mb-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-teal-600 via-teal-700 to-cyan-700 flex items-center justify-center text-white font-bold text-lg shadow-md shadow-teal-700/20 border border-teal-400/30">
            CH
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs uppercase tracking-wider font-semibold text-teal-800">CareerHarness</span>
              <span className="badge-cyan text-[10px] py-0.5 px-2">DeepSeek v4.1</span>
            </div>
            <h1 className="text-xl font-bold text-ink tracking-tight">{title}</h1>
          </div>
        </div>
        <nav className="flex flex-wrap gap-2">
          {links.map(([label, href]) => {
            const isActive = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={`px-3 py-1.5 text-xs font-medium rounded-xl transition-all duration-150 flex items-center gap-1.5 ${
                  isActive
                    ? "neo-pressed text-teal-800 font-semibold shadow-inner border border-teal-500/40"
                    : "neo-raised text-muted hover:text-teal-700 hover:-translate-y-0.5"
                }`}
              >
                {isActive && <span className="h-1.5 w-1.5 rounded-full bg-teal-600 animate-pulse" />}
                {label}
              </Link>
            );
          })}
        </nav>
      </header>
      <main>{children}</main>
    </div>
  );
}

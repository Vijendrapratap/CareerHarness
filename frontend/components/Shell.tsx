"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  CalendarDays,
  ClipboardList,
  Compass,
  MessageSquare,
  Send,
  Settings,
  Sparkles,
  Target,
  type LucideIcon,
} from "lucide-react";
import { Logo } from "@/components/Logo";

const links: [string, string, LucideIcon][] = [
  ["Counsel", "/counsel", Compass],
  ["Jobs", "/jobs", Target],
  ["Applications", "/applications", ClipboardList],
  ["Email Outreach", "/mailbox", Send],
  ["Profile Tips", "/todos", Sparkles],
  ["Inbox", "/inbox", MessageSquare],
  ["Calendar", "/calendar", CalendarDays],
  ["Settings", "/settings", Settings],
];

export function Shell({ title, children }: { title: string; children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="mx-auto max-w-7xl w-full px-4 sm:px-6 lg:px-8 py-4 sm:py-6">
      <header className="neo-raised mb-8 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-3 p-3 pl-4">
        <Link href="/jobs" aria-label="CareerHarness home" className="rounded-xl">
          <Logo />
        </Link>
        <nav aria-label="Main" className="neo-inset flex items-center gap-1 p-1.5 overflow-x-auto max-w-full">
          {links.map(([label, href, Icon]) => {
            const isActive = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                aria-current={isActive ? "page" : undefined}
                className={`flex items-center gap-1.5 shrink-0 min-h-[40px] px-3 text-xs font-bold rounded-xl transition-[color,background-color,box-shadow] duration-150 ${
                  isActive
                    ? "neo-raised !rounded-xl text-ink"
                    : "text-muted hover:text-ink hover:bg-white/50"
                }`}
              >
                <Icon size={15} strokeWidth={2.4} className={isActive ? "text-rope-500" : ""} />
                <span>{label}</span>
              </Link>
            );
          })}
        </nav>
      </header>
      <h1 className="mb-6 px-1 font-display text-3xl sm:text-4xl font-extrabold text-ink">{title}</h1>
      <main className="w-full">{children}</main>
    </div>
  );
}

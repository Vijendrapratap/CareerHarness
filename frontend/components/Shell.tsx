import React from "react";
import Link from "next/link";

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
  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <header className="neo-raised mb-6 flex items-center justify-between px-5 py-4">
        <div>
          <p className="text-xs uppercase tracking-wider text-muted">CareerHarness</p>
          <h1 className="text-xl font-semibold">{title}</h1>
        </div>
        <nav className="flex flex-wrap gap-2">
          {links.map(([label, href]) => (
            <Link key={href} href={href} className="neo-raised px-3 py-2 text-sm font-medium hover:text-accent transition-colors">
              {label}
            </Link>
          ))}
        </nav>
      </header>
      <main>{children}</main>
    </div>
  );
}

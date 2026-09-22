"use client";

import React, { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { api } from "@/lib/api";

interface MessageItem {
  direction: "out" | "in";
  subject: string;
  body: string;
  at: string;
}

interface ThreadItem {
  application_id: string;
  company_name: string;
  job_title?: string;
  messages: MessageItem[];
}

export default function InboxPage() {
  const [threads, setThreads] = useState<ThreadItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadInbox();
  }, []);

  async function loadInbox() {
    setLoading(true);
    setError(null);
    try {
      const data = await api<{ threads: ThreadItem[] }>("/api/tracker/inbox");
      setThreads(data.threads || []);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to load recruiter conversations");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <Shell title="Recruiter Inbox">
      <div className="w-full space-y-6">
        <div className="neo-card p-6 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs uppercase font-bold tracking-wider text-teal-800">
                Communications Loop
              </span>
              <span className="badge-cyan text-[10px] py-0.5 px-2">Bidirectional Sync</span>
            </div>
            <h2 className="text-lg font-bold text-ink tracking-tight">Recruiter Outreach & Inbound Threads</h2>
          </div>
          <span className="neo-inset px-4 py-1.5 text-xs font-bold text-teal-900 rounded-xl">
            Active Threads: {threads.length}
          </span>
        </div>

        {error && (
          <div className="p-4 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-xl">
            {error}
          </div>
        )}

        {loading ? (
          <div className="neo-card p-10 text-center text-muted">
            <div className="inline-block h-6 w-6 rounded-full border-2 border-teal-600 border-t-transparent animate-spin mb-3" />
            <p className="text-sm">Loading recruiter message threads...</p>
          </div>
        ) : threads.length === 0 ? (
          <div className="neo-card p-10 text-center space-y-3">
            <h3 className="text-lg font-bold text-ink">No recruiter conversations yet</h3>
            <p className="text-xs text-muted max-w-md mx-auto">
              When applications are submitted to jobs that provide direct recruiter emails, autonomous outreach drafts and inbound recruiter replies will appear here.
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {threads.map((thread) => (
              <div key={thread.application_id} className="neo-card p-6 space-y-4">
                <div className="flex items-center justify-between border-b border-slate-200/60 pb-3">
                  <div>
                    <h3 className="text-base font-bold text-ink tracking-tight">{thread.company_name}</h3>
                    {thread.job_title && (
                      <span className="badge-teal text-[11px] mt-1 font-semibold">{thread.job_title}</span>
                    )}
                  </div>
                  <span className="badge-cyan text-xs">
                    {thread.messages.length} message{thread.messages.length === 1 ? "" : "s"}
                  </span>
                </div>

                <div className="space-y-3">
                  {thread.messages.map((msg, idx) => (
                    <div
                      key={idx}
                      className={`p-4 rounded-xl border ${
                        msg.direction === "out"
                          ? "neo-inset ml-6 border-l-4 border-l-teal-600 border-slate-200/50 bg-teal-50/20"
                          : "neo-raised mr-6 border-l-4 border-l-emerald-600 border-white bg-emerald-50/20"
                      }`}
                    >
                      <div className="flex items-center justify-between text-xs text-muted mb-1.5">
                        <span
                          className={`text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                            msg.direction === "out"
                              ? "bg-teal-100 text-teal-800"
                              : "bg-emerald-100 text-emerald-800"
                          }`}
                        >
                          {msg.direction === "out" ? "Candidate (Outbound)" : "Recruiter (Inbound)"}
                        </span>
                        <span className="text-[11px] text-muted font-mono">
                          {msg.at
                            ? new Date(msg.at).toLocaleString(undefined, {
                                month: "short",
                                day: "numeric",
                                hour: "2-digit",
                                minute: "2-digit",
                              })
                            : ""}
                        </span>
                      </div>
                      <h4 className="text-xs font-bold text-ink mb-1">{msg.subject}</h4>
                      <p className="text-xs text-ink whitespace-pre-line leading-relaxed">
                        {msg.body}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Shell>
  );
}

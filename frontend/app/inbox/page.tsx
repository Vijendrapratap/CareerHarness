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
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="neo-raised p-6 flex items-center justify-between">
          <div>
            <span className="text-xs uppercase font-semibold tracking-wider text-muted">
              Communications Loop
            </span>
            <h2 className="text-lg font-bold text-ink">Recruiter Conversations & Inbound Threads</h2>
          </div>
          <span className="neo-inset px-4 py-1.5 text-xs font-bold text-ink">
            Active Threads: {threads.length}
          </span>
        </div>

        {error && (
          <div className="p-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl">
            {error}
          </div>
        )}

        {loading ? (
          <div className="neo-raised p-8 text-center text-muted">
            Loading recruiter message threads...
          </div>
        ) : threads.length === 0 ? (
          <div className="neo-raised p-8 text-center space-y-3">
            <h3 className="text-lg font-bold text-ink">No recruiter conversations yet.</h3>
            <p className="text-sm text-muted">
              When applications are submitted to job postings with public recruiter emails, outreach drafts and inbound recruiter replies will appear here.
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {threads.map((thread) => (
              <div key={thread.application_id} className="neo-raised p-6 space-y-4">
                <div className="flex items-center justify-between border-b border-[#c5ced8]/50 pb-3">
                  <div>
                    <h3 className="text-base font-bold text-ink">{thread.company_name}</h3>
                    {thread.job_title && (
                      <p className="text-xs font-semibold text-accent">{thread.job_title}</p>
                    )}
                  </div>
                  <span className="text-xs font-mono text-muted">
                    {thread.messages.length} message{thread.messages.length === 1 ? "" : "s"}
                  </span>
                </div>

                <div className="space-y-3">
                  {thread.messages.map((msg, idx) => (
                    <div
                      key={idx}
                      className={`p-4 rounded-xl ${
                        msg.direction === "out"
                          ? "neo-inset ml-6 border-l-4 border-accent"
                          : "neo-raised mr-6 border-l-4 border-emerald-600"
                      }`}
                    >
                      <div className="flex items-center justify-between text-xs text-muted mb-1">
                        <span className="font-bold uppercase tracking-wider text-ink">
                          {msg.direction === "out" ? "Candidate (Outbound)" : "Recruiter (Inbound)"}
                        </span>
                        <span>
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
                      <h4 className="text-xs font-semibold text-ink mb-1">{msg.subject}</h4>
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

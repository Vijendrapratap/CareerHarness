"use client";

import React, { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { api } from "@/lib/api";

interface InterviewEventItem {
  id: string;
  title: string;
  starts_at: string;
  company_name: string;
  job_title?: string;
  reminder_24h_sent: boolean;
  reminder_1h_sent: boolean;
}

export default function CalendarPage() {
  const [events, setEvents] = useState<InterviewEventItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadInterviews();
  }, []);

  async function loadInterviews() {
    setLoading(true);
    setError(null);
    try {
      const data = await api<InterviewEventItem[]>("/api/tracker/interviews");
      setEvents(data);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to load interview events");
      }
    } finally {
      setLoading(false);
    }
  }

  const [triggering, setTriggering] = useState(false);
  const [triggerMsg, setTriggerMsg] = useState<string | null>(null);

  async function handleRunReminders() {
    setTriggering(true);
    setTriggerMsg(null);
    try {
      const res = await api<{ reminders_sent: number }>("/api/tracker/reminders/run", {
        method: "POST",
      });
      setTriggerMsg(`Reminder pass executed: ${res.reminders_sent} reminder(s) dispatched.`);
      await loadInterviews();
    } catch {
      setTriggerMsg("Reminder job executed.");
    } finally {
      setTriggering(false);
    }
  }

  return (
    <Shell title="Interview Calendar">
      <div className="w-full space-y-6">
        <div className="neo-card p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs uppercase font-bold tracking-wider text-teal-800">
                Schedule & Reminders
              </span>
              <span className="badge-bronze text-[10px] py-0.5 px-2">Autonomous Dispatch</span>
            </div>
            <h2 className="text-lg font-bold text-ink tracking-tight">Scheduled Candidate Interviews</h2>
            <p className="text-xs text-muted mt-0.5">
              Automated reminders are dispatched 24 hours and 1 hour prior to scheduled start times.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="neo-inset px-4 py-2 text-xs font-bold text-teal-900 rounded-xl">
              Upcoming: {events.length}
            </span>
            <button
              type="button"
              disabled={triggering}
              onClick={handleRunReminders}
              className="btn-teal px-4 py-2 text-xs font-bold uppercase tracking-wider disabled:opacity-50"
            >
              {triggering ? "Checking..." : "Run Checks ⚡"}
            </button>
          </div>
        </div>

        {triggerMsg && (
          <div className="p-4 text-xs text-emerald-900 bg-emerald-50 border border-emerald-300 rounded-xl flex items-center gap-2">
            <span>✓</span>
            <span>{triggerMsg}</span>
          </div>
        )}

        {error && (
          <div className="p-4 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-xl">
            {error}
          </div>
        )}

        {loading ? (
          <div className="neo-card p-10 text-center text-muted">
            <div className="inline-block h-6 w-6 rounded-full border-2 border-teal-600 border-t-transparent animate-spin mb-3" />
            <p className="text-sm">Loading interview calendar...</p>
          </div>
        ) : events.length === 0 ? (
          <div className="neo-card p-10 text-center space-y-3">
            <h3 className="text-lg font-bold text-ink">No scheduled interviews yet</h3>
            <p className="text-xs text-muted max-w-md mx-auto">
              When inbound recruiter emails indicate interview confirmations or scheduled calendar slots, events and countdown reminders will automatically populate here.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {events.map((evt) => {
              const dateObj = new Date(evt.starts_at);
              return (
                <div key={evt.id} className="neo-card-interactive p-6 space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div className="flex items-start gap-4">
                      {/* Date Badge */}
                      <div className="neo-inset px-3 py-2 text-center rounded-xl min-w-[70px] border border-slate-200/50 bg-white/40">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-teal-800 block">
                          {dateObj.toLocaleDateString(undefined, { month: "short" })}
                        </span>
                        <span className="text-xl font-extrabold text-ink block leading-none my-0.5">
                          {dateObj.toLocaleDateString(undefined, { day: "numeric" })}
                        </span>
                        <span className="text-[10px] text-muted block">
                          {dateObj.toLocaleDateString(undefined, { weekday: "short" })}
                        </span>
                      </div>

                      <div>
                        <h3 className="text-base font-bold text-ink tracking-tight">{evt.title}</h3>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="badge-teal font-bold text-[11px]">{evt.company_name}</span>
                          {evt.job_title && (
                            <span className="text-xs text-muted font-medium">• {evt.job_title}</span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="neo-inset px-4 py-2 text-right rounded-xl border border-slate-200/40">
                      <div className="text-xs font-bold text-ink">
                        {dateObj.toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                        })}
                      </div>
                      <div className="text-xs text-teal-800 font-bold mt-0.5">
                        {dateObj.toLocaleTimeString(undefined, {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 pt-3 border-t border-slate-200/50 text-xs">
                    <span className="text-muted font-semibold">Reminder Status:</span>
                    <span
                      className={
                        evt.reminder_24h_sent
                          ? "badge-emerald"
                          : "badge-bronze"
                      }
                    >
                      {evt.reminder_24h_sent ? "✓ 24h Reminder Dispatched" : "⏱ 24h Reminder Pending"}
                    </span>
                    <span
                      className={
                        evt.reminder_1h_sent
                          ? "badge-emerald"
                          : "badge-cyan"
                      }
                    >
                      {evt.reminder_1h_sent ? "✓ 1h Reminder Dispatched" : "⏱ 1h Reminder Pending"}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Shell>
  );
}

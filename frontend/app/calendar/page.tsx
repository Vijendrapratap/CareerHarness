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

  return (
    <Shell title="Interview Calendar">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="neo-raised p-6 flex items-center justify-between">
          <div>
            <span className="text-xs uppercase font-semibold tracking-wider text-muted">
              Schedule & Reminders
            </span>
            <h2 className="text-lg font-bold text-ink">Scheduled Candidate Interviews</h2>
            <p className="text-xs text-muted mt-1">
              Automated reminders are dispatched 24 hours and 1 hour before scheduled start times.
            </p>
          </div>
          <span className="neo-inset px-4 py-1.5 text-xs font-bold text-ink">
            Upcoming: {events.length}
          </span>
        </div>

        {error && (
          <div className="p-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl">
            {error}
          </div>
        )}

        {loading ? (
          <div className="neo-raised p-8 text-center text-muted">
            Loading interview calendar...
          </div>
        ) : events.length === 0 ? (
          <div className="neo-raised p-8 text-center space-y-3">
            <h3 className="text-lg font-bold text-ink">No scheduled interviews yet.</h3>
            <p className="text-sm text-muted">
              When inbound recruiter emails indicate an interview confirmation with scheduled times, events will automatically populate here.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {events.map((evt) => {
              const dateObj = new Date(evt.starts_at);
              return (
                <div key={evt.id} className="neo-raised p-6 space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div>
                      <h3 className="text-base font-bold text-ink">{evt.title}</h3>
                      <p className="text-xs font-semibold text-accent mt-0.5">
                        {evt.company_name} {evt.job_title ? `• ${evt.job_title}` : ""}
                      </p>
                    </div>
                    <div className="neo-inset px-4 py-2 text-right">
                      <div className="text-xs font-bold text-ink">
                        {dateObj.toLocaleDateString(undefined, {
                          weekday: "short",
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                        })}
                      </div>
                      <div className="text-xs text-accent font-semibold">
                        {dateObj.toLocaleTimeString(undefined, {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 pt-2 border-t border-[#c5ced8]/40 text-xs">
                    <span className="text-muted font-medium">Automated Reminders:</span>
                    <span
                      className={`px-2 py-0.5 rounded font-semibold ${
                        evt.reminder_24h_sent
                          ? "bg-emerald-100 text-emerald-800"
                          : "bg-[#c5ced8]/30 text-muted"
                      }`}
                    >
                      {evt.reminder_24h_sent ? "✓ 24h Sent" : "24h Pending"}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded font-semibold ${
                        evt.reminder_1h_sent
                          ? "bg-emerald-100 text-emerald-800"
                          : "bg-[#c5ced8]/30 text-muted"
                      }`}
                    >
                      {evt.reminder_1h_sent ? "✓ 1h Sent" : "1h Pending"}
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

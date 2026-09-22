"use client";

import React, { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { api } from "@/lib/api";

interface TrackedApplication {
  id: string;
  company_name: string;
  job_title: string;
  status: string;
  resume_version_id?: string | null;
  is_ghosted: boolean;
  applied_at: string;
  last_activity_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  applied: "badge-cyan",
  acknowledged: "badge-teal",
  interview: "badge-emerald",
  assessment: "badge-teal",
  offer: "badge-emerald font-bold",
  rejected: "bg-slate-200 text-slate-700 px-2.5 py-0.5 rounded-full text-xs font-semibold",
  ghosted: "badge-bronze",
  withdrawn: "bg-slate-200 text-slate-600 px-2.5 py-0.5 rounded-full text-xs font-semibold",
};

export default function ApplicationsPage() {
  const [applications, setApplications] = useState<TrackedApplication[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadApplications();
  }, []);

  async function loadApplications() {
    setLoading(true);
    setError(null);
    try {
      const data = await api<TrackedApplication[]>("/api/tracker/applications");
      setApplications(data);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to load applications");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <Shell title="Submitted Applications">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="neo-card p-6 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs uppercase font-bold tracking-wider text-teal-800">
                Pipeline Management
              </span>
              <span className="badge-teal text-[10px] py-0.5 px-2">Live Tracker</span>
            </div>
            <h2 className="text-lg font-bold text-ink tracking-tight">Active Candidate Applications</h2>
          </div>
          <span className="neo-inset px-4 py-1.5 text-xs font-bold text-teal-900 rounded-xl">
            Total: {applications.length}
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
            <p className="text-sm">Loading your application pipeline...</p>
          </div>
        ) : applications.length === 0 ? (
          <div className="neo-card p-10 text-center space-y-3">
            <h3 className="text-lg font-bold text-ink">No applications in pipeline yet</h3>
            <p className="text-xs text-muted max-w-md mx-auto">
              Discover matching jobs on the Jobs board and submit an application packet to track status, recruiter outreach, and interview reminders here.
            </p>
            <button
              onClick={() => window.location.assign("/jobs")}
              className="btn-teal px-6 py-2.5 text-xs font-bold uppercase tracking-wider mt-2"
            >
              Browse Scouted Jobs →
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {applications.map((app) => (
              <div key={app.id} className="neo-card-interactive p-6 space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <h3 className="text-base font-bold text-ink tracking-tight">{app.job_title}</h3>
                    <p className="text-xs font-bold text-teal-800 mt-0.5">{app.company_name}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs font-bold uppercase ${
                        STATUS_COLORS[app.status] || "badge-teal"
                      }`}
                    >
                      {app.status}
                    </span>
                    {app.is_ghosted && (
                      <span className="badge-bronze">
                        ⚠️ Silence (&gt;10d)
                      </span>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-muted pt-3 border-t border-slate-200/50">
                  <div>
                    <span className="font-semibold text-ink">Applied Date:</span>{" "}
                    {new Date(app.applied_at).toLocaleDateString(undefined, {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                    })}
                  </div>
                  <div>
                    <span className="font-semibold text-ink">Resume Version:</span>{" "}
                    <span className="font-mono text-xs text-teal-800 bg-white/50 px-2 py-0.5 rounded border border-slate-200/40">
                      {app.resume_version_id ? `${app.resume_version_id.slice(0, 12)}...` : "Master Resume"}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Shell>
  );
}

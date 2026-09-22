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
  applied: "bg-blue-100 text-blue-800",
  acknowledged: "bg-indigo-100 text-indigo-800",
  interview: "bg-emerald-100 text-emerald-800",
  assessment: "bg-purple-100 text-purple-800",
  offer: "bg-green-100 text-green-900 font-bold",
  rejected: "bg-slate-200 text-slate-700",
  ghosted: "bg-amber-100 text-amber-800",
  withdrawn: "bg-gray-100 text-gray-600",
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
        <div className="neo-raised p-6 flex items-center justify-between">
          <div>
            <span className="text-xs uppercase font-semibold tracking-wider text-muted">
              Pipeline Management
            </span>
            <h2 className="text-lg font-bold text-ink">Active Candidate Applications</h2>
          </div>
          <span className="neo-inset px-4 py-1.5 text-xs font-bold text-ink">
            Total: {applications.length}
          </span>
        </div>

        {error && (
          <div className="p-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl">
            {error}
          </div>
        )}

        {loading ? (
          <div className="neo-raised p-8 text-center text-muted">Loading your pipeline...</div>
        ) : applications.length === 0 ? (
          <div className="neo-raised p-8 text-center space-y-3">
            <h3 className="text-lg font-bold text-ink">No applications yet.</h3>
            <p className="text-sm text-muted">
              Discover matching jobs on the Jobs board and submit an honest application packet to track it here.
            </p>
            <button
              onClick={() => window.location.assign("/jobs")}
              className="neo-pressed px-5 py-2.5 text-xs font-semibold uppercase tracking-wider text-accent mt-2"
            >
              Browse Jobs Board →
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {applications.map((app) => (
              <div key={app.id} className="neo-raised p-6 space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <h3 className="text-base font-bold text-ink">{app.job_title}</h3>
                    <p className="text-xs font-semibold text-accent mt-0.5">{app.company_name}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs px-2.5 py-1 rounded-full font-bold uppercase ${
                        STATUS_COLORS[app.status] || "bg-gray-100 text-gray-800"
                      }`}
                    >
                      {app.status}
                    </span>
                    {app.is_ghosted && (
                      <span className="text-xs px-2 py-0.5 rounded font-bold uppercase bg-amber-200 text-amber-900">
                        Ghosted (&gt;10d silence)
                      </span>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-muted pt-2 border-t border-[#c5ced8]/40">
                  <div>
                    <span className="font-semibold text-ink">Applied:</span>{" "}
                    {new Date(app.applied_at).toLocaleDateString(undefined, {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                    })}
                  </div>
                  <div>
                    <span className="font-semibold text-ink">Resume Version:</span>{" "}
                    <span className="font-mono text-xs text-ink">{app.resume_version_id || "Master"}</span>
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

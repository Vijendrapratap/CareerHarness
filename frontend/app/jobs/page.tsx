"use client";

import React, { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { api } from "@/lib/api";

interface JobMatchItem {
  match_id: string;
  job_id: string;
  title: string;
  company: string;
  match_score: number;
  why_matched: string;
  status: string;
}

interface JourneyState {
  stage: string;
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobMatchItem[]>([]);
  const [stage, setStage] = useState<string>("counsel");
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scanMessage, setScanMessage] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [jobsData, journeyData] = await Promise.all([
        api<JobMatchItem[]>("/api/jobs"),
        api<JourneyState>("/api/journey").catch(() => ({ stage: "hunt" })),
      ]);
      setJobs(jobsData);
      setStage(journeyData.stage);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to load matched jobs");
      }
    } finally {
      setLoading(false);
    }
  }

  const isScanDisabled = ["counsel", "todos", "mailbox"].includes(stage);

  async function handleScanNow() {
    if (isScanDisabled) return;
    setScanning(true);
    setError(null);
    setScanMessage(null);
    try {
      const res = await fetch("/api/scout/scan-now", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Scout scan failed");
      }
      setScanMessage(data.message || `Scout scan completed. Found ${data.scraped_count ?? 0} jobs.`);
      await loadData();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Scout scan failed");
      }
    } finally {
      setScanning(false);
    }
  }

  return (
    <Shell title="Scouted Jobs Board">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Scout Trigger Header */}
        <div className="neo-raised p-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <span className="text-xs uppercase font-semibold tracking-wider text-muted">
              Live ATS Discovery
            </span>
            <h2 className="text-lg font-bold text-ink">Autonomous ATS Match Feed</h2>
            <p className="text-xs text-muted mt-1">
              Scouts Greenhouse, Lever, and Ashby postings grounded in your verified target roles.
            </p>
          </div>
          <div>
            <button
              onClick={handleScanNow}
              disabled={isScanDisabled || scanning}
              className={`neo-pressed px-5 py-2.5 text-xs font-bold uppercase tracking-wider transition-all ${
                isScanDisabled
                  ? "opacity-50 cursor-not-allowed text-muted"
                  : "text-accent hover:opacity-90"
              }`}
            >
              {scanning ? "Scanning Portals..." : "Trigger Scout Now"}
            </button>
          </div>
        </div>

        {isScanDisabled && (
          <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-800">
            Scouting is locked while in the <strong>{stage}</strong> stage. Clear your profile checklist and connect a mailbox to unlock.
          </div>
        )}

        {error && (
          <div className="p-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl">
            {error}
          </div>
        )}

        {scanMessage && (
          <div className="p-4 text-sm text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-xl">
            {scanMessage}
          </div>
        )}

        {/* Job Matches Listing */}
        {loading ? (
          <div className="neo-raised p-8 text-center text-muted">Loading scouted jobs...</div>
        ) : jobs.length === 0 ? (
          <div className="neo-raised p-8 text-center space-y-3">
            <h3 className="text-lg font-bold text-ink">No Matched Jobs Yet</h3>
            <p className="text-sm text-muted">
              Trigger a scout scan above to discover matching roles from public ATS pipelines.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {jobs.map((item) => (
              <div key={item.match_id} className="neo-raised p-6 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <h3 className="text-base font-bold text-ink">{item.title}</h3>
                    <p className="text-xs font-semibold text-accent mt-0.5">{item.company}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="neo-inset px-3 py-1 text-xs font-bold text-ink">
                      Fit: {item.match_score.toFixed(1)} / 10
                    </span>
                    <span className="text-xs uppercase px-2 py-0.5 rounded font-semibold text-muted bg-[#c5ced8]/30">
                      {item.status}
                    </span>
                  </div>
                </div>

                <div className="neo-inset p-3 text-xs text-muted">
                  <span className="font-semibold text-ink block mb-0.5">Matching Rationale:</span>
                  {item.why_matched || "Matched based on core baseline skill alignment and title match."}
                </div>

                {/* Apply Buttons (Disabled for Task 7, wired in Task 8) */}
                <div className="flex items-center justify-end gap-3 pt-2">
                  <button
                    type="button"
                    disabled={true}
                    className="neo-raised px-4 py-2 text-xs font-medium text-muted opacity-60 cursor-not-allowed"
                    title="Will be enabled in Task 8"
                  >
                    Use my resume
                  </button>
                  <button
                    type="button"
                    disabled={true}
                    className="neo-pressed px-4 py-2 text-xs font-semibold text-accent opacity-60 cursor-not-allowed"
                    title="Will be enabled in Task 8"
                  >
                    Refine for this job
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Shell>
  );
}

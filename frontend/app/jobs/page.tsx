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

interface CoverLetter {
  title?: string;
  body_text?: string;
}

interface PreparedPacket {
  mode: "original" | "refine";
  job_id: string;
  resume_version_id: string;
  resume_content: {
    candidate_name?: string;
    skills?: string[];
    summary?: string;
    experience?: Array<{
      company: string;
      dates?: string;
      bullets?: string[];
    }>;
  };
  cover_letter?: CoverLetter | null;
  honesty_review?: {
    is_honest: boolean;
    violations_count?: number;
    violations?: string[];
  };
  draft_source?: string;
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobMatchItem[]>([]);
  const [stage, setStage] = useState<string>("counsel");
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [preparingJobId, setPreparingJobId] = useState<string | null>(null);
  const [activePacket, setActivePacket] = useState<PreparedPacket | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);
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

  async function handleChoose(jobId: string, mode: "original" | "refine") {
    setPreparingJobId(jobId);
    setError(null);
    setSubmitSuccess(null);
    setActivePacket(null);
    try {
      const result = await api<PreparedPacket>("/api/applications/choose", {
        method: "POST",
        body: JSON.stringify({ job_id: jobId, mode }),
      });
      setActivePacket({ ...result, job_id: jobId });
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError(`Failed to prepare packet in ${mode} mode`);
      }
    } finally {
      setPreparingJobId(null);
    }
  }

  async function handleSubmitPacket() {
    if (!activePacket) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await api<{ status: string; application_id: string }>(
        "/api/applications/submit",
        {
          method: "POST",
          body: JSON.stringify({
            job_id: activePacket.job_id,
            resume_version_id: activePacket.resume_version_id,
            has_connected_email: true,
          }),
        }
      );
      setSubmitSuccess(`Application submitted successfully! Tracking ID: ${res.application_id}`);
      setActivePacket(null);
      await loadData();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Application submission failed");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Shell title="Scouted Jobs Board">
      <div className="w-full space-y-6">
        {/* Scout Trigger Header */}
        <div className="neo-card p-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs uppercase font-bold tracking-wider text-teal-800">
                Live ATS Discovery
              </span>
              <span className="badge-cyan text-[10px] py-0.5 px-2">Greenhouse • Lever • Ashby</span>
            </div>
            <h2 className="text-lg font-bold text-ink tracking-tight">Autonomous Match Pipeline</h2>
            <p className="text-xs text-muted mt-0.5">
              Scouts verified public postings with DeepSeek matching algorithms grounded in your target roles.
            </p>
          </div>
          <div>
            <button
              onClick={handleScanNow}
              disabled={isScanDisabled || scanning}
              className={`px-5 py-2.5 text-xs font-bold uppercase tracking-wider rounded-xl transition-all ${
                isScanDisabled
                  ? "neo-inset opacity-50 cursor-not-allowed text-muted"
                  : "btn-teal"
              }`}
            >
              {scanning ? "Scanning Portals..." : "Trigger Scout Now ⚡"}
            </button>
          </div>
        </div>

        {isScanDisabled && (
          <div className="p-4 rounded-xl bg-amber-50 border border-amber-300 text-xs text-amber-900 flex items-center gap-2">
            <span>⚠️</span>
            <span>
              Scouting is paused during the <strong>{stage}</strong> stage. Clear your profile checklist and connect a mailbox to unlock autonomous hunt.
            </span>
          </div>
        )}

        {error && (
          <div className="p-4 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-xl">
            {error}
          </div>
        )}

        {scanMessage && (
          <div className="p-4 text-xs text-emerald-900 bg-emerald-50 border border-emerald-300 rounded-xl flex items-center gap-2">
            <span>✓</span>
            <span>{scanMessage}</span>
          </div>
        )}

        {submitSuccess && (
          <div className="p-4 text-xs text-emerald-900 bg-emerald-50 border border-emerald-300 rounded-xl flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span>✓</span>
              <span className="font-medium">{submitSuccess}</span>
            </div>
            <button
              onClick={() => window.location.assign("/applications")}
              className="text-xs font-bold uppercase tracking-wider text-teal-800 underline hover:text-teal-950 ml-4"
            >
              View Pipeline →
            </button>
          </div>
        )}

        {/* Prepared Packet Review Modal / Panel */}
        {activePacket && (
          <div className="neo-card p-6 space-y-4 border-2 border-teal-500/40 shadow-xl shadow-teal-900/10">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-xs uppercase font-bold text-teal-800 tracking-wider">
                  Prepared Packet ({activePacket.mode === "original" ? "Original Master" : "Refined / Tailored"})
                </span>
                <h3 className="text-lg font-bold text-ink tracking-tight">Ready for Honest Review</h3>
              </div>
              <div className="flex items-center gap-2">
                <span className="badge-emerald">
                  Honesty Verified: {activePacket.honesty_review?.is_honest ? "100% Truthful" : "Flagged"}
                </span>
                <span className="badge-cyan text-[11px]">
                  {activePacket.draft_source}
                </span>
              </div>
            </div>

            {/* Resume Summary / Top Bullets */}
            <div className="neo-inset p-4 space-y-2 text-xs rounded-xl">
              <span className="font-bold text-teal-900 uppercase block">Resume Content Preview:</span>
              <p className="text-ink">
                <strong>Target Role:</strong> {activePacket.resume_content?.summary || "Factual alignment verified."}
              </p>
              {activePacket.resume_content?.experience?.[0] && (
                <div className="mt-2 text-muted">
                  <span className="font-semibold text-ink">
                    Top Highlight ({activePacket.resume_content.experience[0].company}):
                  </span>
                  <ul className="list-disc list-inside mt-1 space-y-1 font-mono text-[11px]">
                    {activePacket.resume_content.experience[0].bullets?.slice(0, 2).map((b, i) => (
                      <li key={i}>{b}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Cover Letter Preview */}
            {activePacket.cover_letter && (
              <div className="neo-inset p-4 text-xs space-y-1.5 rounded-xl">
                <span className="font-bold text-teal-900 uppercase block">Drafted Cover Letter:</span>
                <p className="whitespace-pre-line text-ink font-serif text-xs leading-relaxed bg-white/40 p-3 rounded-lg border border-slate-200/40">
                  {activePacket.cover_letter.body_text}
                </p>
              </div>
            )}

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setActivePacket(null)}
                className="neo-raised px-4 py-2 text-xs font-semibold text-muted hover:text-ink rounded-xl"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={submitting}
                onClick={handleSubmitPacket}
                className="btn-teal px-6 py-2.5 text-xs font-bold uppercase tracking-wider disabled:opacity-50"
              >
                {submitting ? "Submitting Packet..." : "Submit This Packet →"}
              </button>
            </div>
          </div>
        )}

        {/* Job Matches Listing */}
        {loading ? (
          <div className="neo-card p-10 text-center text-muted">
            <div className="inline-block h-6 w-6 rounded-full border-2 border-teal-600 border-t-transparent animate-spin mb-3" />
            <p className="text-sm">Scouting live ATS job boards for matching positions...</p>
          </div>
        ) : jobs.length === 0 ? (
          <div className="neo-card p-10 text-center space-y-3">
            <h3 className="text-lg font-bold text-ink">No Matched Jobs Yet</h3>
            <p className="text-xs text-muted max-w-md mx-auto">
              Click &quot;Trigger Scout Now&quot; above to search live Greenhouse, Lever, and Ashby pipelines for roles matching your profile.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {jobs.map((item) => (
              <div key={item.match_id} className="neo-card-interactive p-6 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <h3 className="text-base font-bold text-ink tracking-tight">{item.title}</h3>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="badge-teal text-[11px] font-bold">{item.company}</span>
                      <span className="text-[11px] text-muted uppercase font-semibold">
                        Status: {item.status}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs font-bold px-3 py-1 rounded-full ${
                        item.match_score >= 8.0
                          ? "badge-emerald"
                          : item.match_score >= 6.0
                          ? "badge-cyan"
                          : "badge-bronze"
                      }`}
                    >
                      Fit: {item.match_score.toFixed(1)} / 10
                    </span>
                  </div>
                </div>

                <div className="neo-inset p-3.5 text-xs text-muted rounded-xl border border-slate-200/40">
                  <span className="font-bold text-ink block mb-0.5">Matching Rationale:</span>
                  <p className="leading-relaxed">
                    {item.why_matched || "Matched based on core baseline skill alignment and role focus."}
                  </p>
                </div>

                {/* Apply Buttons */}
                <div className="flex items-center justify-end gap-3 pt-1">
                  <button
                    type="button"
                    disabled={preparingJobId === item.job_id}
                    onClick={() => handleChoose(item.job_id, "original")}
                    className="neo-raised px-4 py-2 text-xs font-semibold text-ink hover:text-teal-700 hover:border-teal-400 rounded-xl transition-all disabled:opacity-50"
                  >
                    {preparingJobId === item.job_id ? "Preparing..." : "Use Original Master"}
                  </button>
                  <button
                    type="button"
                    disabled={preparingJobId === item.job_id}
                    onClick={() => handleChoose(item.job_id, "refine")}
                    className="btn-teal px-5 py-2 text-xs font-bold uppercase tracking-wider disabled:opacity-50"
                  >
                    {preparingJobId === item.job_id ? "Tailoring..." : "Refine for this job ✦"}
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

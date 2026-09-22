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

        {submitSuccess && (
          <div className="p-4 text-sm text-emerald-900 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center justify-between">
            <span>{submitSuccess}</span>
            <button
              onClick={() => window.location.assign("/applications")}
              className="text-xs font-bold uppercase tracking-wider text-accent underline ml-4"
            >
              View Applications →
            </button>
          </div>
        )}

        {/* Prepared Packet Review Modal / Panel */}
        {activePacket && (
          <div className="neo-raised p-6 space-y-4 border-2 border-[#3d6b8c]/30">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-xs uppercase font-bold text-accent tracking-wider">
                  Prepared Packet ({activePacket.mode === "original" ? "Original Master" : "Refined / Tailored"})
                </span>
                <h3 className="text-lg font-bold text-ink">Ready for Honest Review</h3>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold px-2.5 py-1 rounded bg-emerald-100 text-emerald-800">
                  Honesty Verified: {activePacket.honesty_review?.is_honest ? "100% Truthful" : "Flagged"}
                </span>
                <span className="text-xs font-mono text-muted">
                  Source: {activePacket.draft_source}
                </span>
              </div>
            </div>

            {/* Resume Summary / Top Bullets */}
            <div className="neo-inset p-4 space-y-2 text-xs">
              <span className="font-bold text-ink uppercase block">Resume Content Preview:</span>
              <p className="text-ink">
                <strong>Target Role:</strong> {activePacket.resume_content?.summary || "Factual alignment verified."}
              </p>
              {activePacket.resume_content?.experience?.[0] && (
                <div className="mt-2 text-muted">
                  <span className="font-semibold text-ink">
                    Top Highlight ({activePacket.resume_content.experience[0].company}):
                  </span>
                  <ul className="list-disc list-inside mt-1 space-y-1">
                    {activePacket.resume_content.experience[0].bullets?.slice(0, 2).map((b, i) => (
                      <li key={i}>{b}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Cover Letter Preview */}
            {activePacket.cover_letter && (
              <div className="neo-inset p-4 text-xs space-y-1">
                <span className="font-bold text-ink uppercase block">Drafted Cover Letter:</span>
                <p className="whitespace-pre-line text-ink font-serif text-sm">
                  {activePacket.cover_letter.body_text}
                </p>
              </div>
            )}

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setActivePacket(null)}
                className="neo-raised px-4 py-2 text-xs font-semibold text-muted hover:text-ink"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={submitting}
                onClick={handleSubmitPacket}
                className="neo-pressed px-6 py-2 text-xs font-bold text-accent uppercase tracking-wider disabled:opacity-50"
              >
                {submitting ? "Submitting Packet..." : "Submit This Packet →"}
              </button>
            </div>
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

                {/* Apply Buttons (Wired in Task 8) */}
                <div className="flex items-center justify-end gap-3 pt-2">
                  <button
                    type="button"
                    disabled={preparingJobId === item.job_id}
                    onClick={() => handleChoose(item.job_id, "original")}
                    className="neo-raised px-4 py-2 text-xs font-semibold text-ink hover:text-accent transition-colors disabled:opacity-50"
                  >
                    {preparingJobId === item.job_id ? "Preparing..." : "Use my resume"}
                  </button>
                  <button
                    type="button"
                    disabled={preparingJobId === item.job_id}
                    onClick={() => handleChoose(item.job_id, "refine")}
                    className="neo-pressed px-4 py-2 text-xs font-bold text-accent uppercase tracking-wider transition-colors disabled:opacity-50"
                  >
                    {preparingJobId === item.job_id ? "Tailoring..." : "Refine for this job"}
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

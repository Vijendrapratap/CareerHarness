"use client";

import React, { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { api } from "@/lib/api";
import { APPLY_LINE, JobFitCard, type JobItem } from "@/components/JobFitCard";

interface SkillFix {
  skill: string;
  in_resume: boolean;
  jobs_unlocked: number;
  jobs_improved: number;
  avg_gain: number;
}

type Tab = "ready" | "stretch" | "skip";
const SCAN_POLLS = 12; // ~1 minute
const SOURCES = ["Greenhouse", "Lever", "Ashby", "Workday", "RemoteOK", "Remotive", "Himalayas", "Arbeitnow", "HN Hiring"];

function tabOf(job: JobItem): Tab {
  if (!job.fit) return "stretch";
  if (job.fit.score >= APPLY_LINE) return "ready";
  return job.fit.verdict === "stretch" ? "stretch" : "skip";
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
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [emailConnected, setEmailConnected] = useState<boolean | null>(null);
  const [fixes, setFixes] = useState<SkillFix[]>([]);
  const [busySkill, setBusySkill] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab | null>(null);
  const [scanPolls, setScanPolls] = useState(0);
  const [jobsBeforeScan, setJobsBeforeScan] = useState<number | null>(null);

  // After "Scan again" the scan runs server-side; refresh quietly until it has had time to finish.
  useEffect(() => {
    if (scanPolls <= 0) return;
    const t = setTimeout(async () => {
      const [jobList, fixList] = await Promise.all([
        api<JobItem[]>("/api/jobs").catch(() => null),
        api<SkillFix[]>("/api/fit/fixes").catch(() => null),
      ]);
      if (jobList) setJobs(jobList);
      if (fixList) setFixes(fixList);
      if (scanPolls === 1 && jobList && jobsBeforeScan !== null) {
        const added = jobList.length - jobsBeforeScan;
        setScanMessage(added > 0 ? `Scan finished: ${added} new match${added === 1 ? "" : "es"}.` : "Scan finished: no new matches this time.");
      }
      setScanPolls((n) => n - 1);
    }, 5000);
    return () => clearTimeout(t);
  }, [scanPolls, jobsBeforeScan]);
  const [scoutPolls, setScoutPolls] = useState(0);
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
    api<{ connected: unknown }>("/api/emails/status")
      .then((s) => setEmailConnected(Boolean(s.connected)))
      .catch(() => setEmailConnected(null));
  }, []);

  // Scout starts in the background when roles are saved: poll briefly until first matches land.
  const scoutSearching = !loading && jobs.length === 0 && scoutPolls < 12;
  useEffect(() => {
    if (!scoutSearching) return;
    const t = setTimeout(async () => {
      const latest = await api<JobItem[]>("/api/jobs").catch(() => []);
      setJobs(latest);
      setScoutPolls((n) => n + 1);
    }, 5000);
    return () => clearTimeout(t);
  }, [scoutSearching, scoutPolls]);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [jobList, fixList] = await Promise.all([
        api<JobItem[]>("/api/jobs"),
        api<SkillFix[]>("/api/fit/fixes").catch(() => []),
      ]);
      setJobs(jobList);
      setFixes(fixList);
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

  async function handleScanNow() {
    setScanning(true);
    setError(null);
    setScanMessage(null);
    try {
      const data = await api<{ scans_remaining: number }>("/api/scout/scan-now", { method: "POST" });
      setJobsBeforeScan(jobs.length);
      setScanPolls(SCAN_POLLS);
      setScanMessage(
        `Scanning company boards, Workday sites, remote job boards and HN. New matches appear here as they're scored. ` +
          `${data.scans_remaining} manual scan${data.scans_remaining === 1 ? "" : "s"} left today.`
      );
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

  async function handleSkill(skill: string, action: "confirm" | "decline") {
    setBusySkill(skill);
    setError(null);
    setScanMessage(null);
    try {
      const res = await api<{ unlocked?: number; apply_ready: number }>(`/api/fit/fixes/${action}-skill`, {
        method: "POST",
        body: JSON.stringify({ skill }),
      });
      setScanMessage(
        action === "confirm"
          ? `Confirmed ${skill}. ${res.unlocked ? `${res.unlocked} more job${res.unlocked === 1 ? "" : "s"} ready to apply — ` : ""}${res.apply_ready} ready in total.`
          : `Noted: ${skill} stays a gap. We won't suggest it again.`
      );
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not update that skill");
    } finally {
      setBusySkill(null);
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

  const counts = { ready: 0, stretch: 0, skip: 0 };
  jobs.forEach((j) => counts[tabOf(j)]++);
  const activeTab: Tab = tab ?? (counts.ready > 0 ? "ready" : counts.stretch > 0 ? "stretch" : "skip");
  const visibleJobs = jobs.filter((j) => tabOf(j) === activeTab);

  return (
    <Shell title="Your Job Matches">
      <div className="w-full space-y-6">
        {/* Scout Trigger Header */}
        <div className="neo-card p-6 flex flex-col sm:flex-row items-center justify-between gap-4 border border-white/80 bg-white/70 backdrop-blur-md shadow-md">
          <div>
            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
              <span className="text-xs uppercase font-bold tracking-wider text-teal-900">
                Sources
              </span>
              {SOURCES.map((src) => (
                <span key={src} className="badge-sky text-[10px] py-0.5 px-2">{src}</span>
              ))}
            </div>
            <h2 className="text-lg font-bold text-ink tracking-tight">Scout is watching {SOURCES.length} sources for you</h2>
            <p className="text-xs text-muted mt-0.5">
              Fresh postings (last 30 days) that match your roles, work mode and locations, de-duplicated across sources.
              Add companies you love in Counsel and Scout watches their boards too.
            </p>
          </div>
          <div>
            <button
              onClick={handleScanNow}
              disabled={scanning || scanPolls > 0}
              className="px-6 py-3 text-xs font-bold uppercase tracking-wider rounded-xl transition-all shadow-md btn-amber hover:shadow-lg hover:shadow-amber-500/25 active:scale-[0.97] disabled:opacity-60"
            >
              {scanning ? "Starting..." : scanPolls > 0 ? "Scanning..." : "Scan Again Now ⚡"}
            </button>
          </div>
        </div>

        {scoutSearching && (
          <div className="p-4 rounded-xl bg-sky-50 border border-sky-300 text-xs text-sky-900 flex items-center gap-2">
            <span className="h-3 w-3 rounded-full border-2 border-sky-600 border-t-transparent animate-spin" />
            <span>Scout is searching company job boards for your target roles. Matches appear here automatically.</span>
          </div>
        )}

        {emailConnected === false && (
          <div className="p-4 rounded-xl bg-white/80 border border-slate-200 text-xs text-ink flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <span>
              <strong>Optional:</strong> connect your email and we can also reach out to recruiters for you. Every email waits for your approval.
            </span>
            <a href="/mailbox" className="font-bold text-teal-800 underline whitespace-nowrap">
              Connect email →
            </a>
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
              {scoutSearching
                ? "Scout is still searching — this usually takes under a minute."
                : "No postings matched your roles on the boards we scan yet. Try \u201cScan Again Now\u201d, or broaden your target roles in Counsel."}
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {fixes.some((f) => f.jobs_unlocked > 0 || f.jobs_improved > 1) && (
              <section className="neo-card p-5 sm:p-6 space-y-3 border-rope-500/20">
                <div>
                  <h2 className="text-lg font-bold text-ink">Biggest wins for your profile</h2>
                  <p className="text-xs text-muted">
                    Confirm skills you&apos;ve really used — every job is rescored instantly. Skipped fixes keep scores honest.
                  </p>
                </div>
                <div className="grid sm:grid-cols-3 gap-3">
                  {fixes.slice(0, 3).map((f) => (
                    <div key={f.skill} className="neo-raised p-4 space-y-2">
                      <p className="font-display text-base font-bold text-ink">{f.skill}</p>
                      <p className="text-xs text-muted">
                        {f.jobs_unlocked > 0 ? (
                          <span className="font-bold text-teal-700">Unlocks {f.jobs_unlocked} job{f.jobs_unlocked === 1 ? "" : "s"}</span>
                        ) : (
                          <span className="font-semibold text-ink">+{f.avg_gain.toFixed(1)} avg</span>
                        )}{" "}
                        · improves {f.jobs_improved}
                        {f.in_resume && " · in your resume"}
                      </p>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          disabled={busySkill !== null}
                          onClick={() => handleSkill(f.skill, "confirm")}
                          className="btn-teal flex-1 px-3 py-1.5 text-[11px] disabled:opacity-50"
                        >
                          {busySkill === f.skill ? "Saving..." : "I have it"}
                        </button>
                        <button
                          type="button"
                          disabled={busySkill !== null}
                          onClick={() => handleSkill(f.skill, "decline")}
                          className="neo-raised !rounded-xl px-3 py-1.5 text-[11px] font-bold text-muted hover:text-ink disabled:opacity-50"
                        >
                          Not yet
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            <div role="tablist" aria-label="Filter jobs by fit" className="neo-inset inline-flex gap-1 p-1.5">
              {(["ready", "stretch", "skip"] as Tab[]).map((t) => {
                const count = jobs.filter((j) => tabOf(j) === t).length;
                const active = activeTab === t;
                return (
                  <button
                    key={t}
                    role="tab"
                    aria-selected={active}
                    onClick={() => setTab(t)}
                    className={`px-3.5 py-2 text-xs font-bold rounded-xl transition-colors ${
                      active ? "neo-raised !rounded-xl text-ink" : "text-muted hover:text-ink"
                    }`}
                  >
                    {t === "ready" ? "Ready to apply" : t === "stretch" ? "Stretch" : "Not a fit yet"}{" "}
                    <span className="tabular-nums opacity-70">{count}</span>
                  </button>
                );
              })}
            </div>

            {visibleJobs.length === 0 && (
              <p className="neo-card p-6 text-center text-xs text-muted">
                {activeTab === "ready"
                  ? "Nothing clears the 4.0 apply line yet — confirm skills above or check the Stretch tab."
                  : "No jobs here."}
              </p>
            )}
            {visibleJobs.map((item) => (
              <JobFitCard
                key={item.match_id}
                item={item}
                preparing={preparingJobId === item.job_id}
                busySkill={busySkill}
                onChoose={handleChoose}
                onConfirm={(skill) => handleSkill(skill, "confirm")}
                onDecline={(skill) => handleSkill(skill, "decline")}
              />
            ))}
          </div>
        )}
      </div>
    </Shell>
  );
}

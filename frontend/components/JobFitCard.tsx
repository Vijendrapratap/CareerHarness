"use client";

import React from "react";
import { Check, ExternalLink, HelpCircle, Lock, X } from "lucide-react";

export const APPLY_LINE = 4.0;

export interface Requirement {
  skill: string;
  importance: "critical" | "high" | "preferred";
  match: "verified" | "unconfirmed" | "gap";
}

export interface Fix {
  kind: "confirm_skill";
  skill: string;
  gain: number;
  in_resume: boolean;
}

export interface FitReport {
  score: number;
  verdict: "apply" | "stretch" | "skip";
  requirements: Requirement[];
  gates: string[];
  strengths: string[];
  gaps: string[];
  fixes: Fix[];
}

export interface JobItem {
  match_id: string;
  job_id: string;
  title: string;
  company: string;
  location: string;
  url: string;
  why_matched: string;
  status: string;
  fit: FitReport | null;
}

const VERDICT = {
  apply: { label: "Ready to apply", className: "badge-teal" },
  stretch: { label: "Stretch", className: "badge-amber" },
  skip: { label: "Not a fit yet", className: "badge-sky" },
} as const;

/** Sunken track filled to the score, with the rope-orange apply line at 4.0. */
function FitGauge({ score }: { score: number }) {
  const pct = (Math.max(1, Math.min(5, score)) - 1) / 4;
  const linePct = (APPLY_LINE - 1) / 4;
  return (
    <div className="w-full" aria-label={`Fit ${score} out of 5; apply line is ${APPLY_LINE}`}>
      <div className="relative h-2.5 neo-inset !rounded-full overflow-visible">
        <div
          className={`absolute inset-y-0 left-0 rounded-full ${score >= APPLY_LINE ? "bg-teal-600" : "bg-slate-400"}`}
          style={{ width: `${pct * 100}%` }}
        />
        <div
          className="absolute -top-1 -bottom-1 w-[3px] rounded-full bg-rope-500"
          style={{ left: `calc(${linePct * 100}% - 1.5px)` }}
        />
      </div>
      <div className="relative h-4 text-[10px] font-bold text-rope-600">
        <span className="absolute -translate-x-1/2" style={{ left: `${linePct * 100}%` }}>
          apply line
        </span>
      </div>
    </div>
  );
}

function RequirementChip({ req }: { req: Requirement }) {
  const Icon = req.match === "verified" ? Check : req.match === "unconfirmed" ? HelpCircle : X;
  const tone =
    req.match === "verified"
      ? "bg-teal-50 text-teal-900 border-teal-300"
      : req.match === "unconfirmed"
      ? "bg-orange-50 text-orange-700 border-orange-200"
      : "bg-white/70 text-muted border-slate-200";
  return (
    <span
      title={`${req.importance} · ${req.match === "unconfirmed" ? "in your resume, not confirmed" : req.match}`}
      className={`inline-flex items-center gap-1 px-2 py-1 rounded-lg border text-[11px] ${tone} ${
        req.importance === "preferred" ? "font-medium opacity-80" : "font-bold"
      }`}
    >
      <Icon size={12} strokeWidth={3} />
      {req.skill}
      {req.importance === "critical" && <span className="text-[9px] uppercase tracking-wider opacity-70">key</span>}
    </span>
  );
}

export function JobFitCard({
  item,
  preparing,
  busySkill,
  onChoose,
  onConfirm,
  onDecline,
}: {
  item: JobItem;
  preparing: boolean;
  busySkill: string | null;
  onChoose: (jobId: string, mode: "original" | "refine") => void;
  onConfirm: (skill: string) => void;
  onDecline: (skill: string) => void;
}) {
  const fit = item.fit;
  const canApply = !!fit && fit.score >= APPLY_LINE;
  const verdict = fit ? VERDICT[fit.verdict] : null;

  return (
    <article className="neo-card-interactive p-5 sm:p-6 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="text-lg font-bold text-ink leading-snug">{item.title}</h3>
          <div className="flex flex-wrap items-center gap-2 mt-1.5 text-xs text-muted">
            <span className="badge-teal">{item.company}</span>
            {item.location && <span className="truncate max-w-[18rem]">{item.location}</span>}
            {item.url && (
              <a href={item.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-semibold text-teal-800 hover:underline">
                Posting <ExternalLink size={12} />
              </a>
            )}
          </div>
        </div>
        {fit && (
          <div className="sm:w-56 shrink-0">
            <div className="flex items-baseline justify-between mb-1.5">
              <span className="font-display text-3xl font-extrabold text-ink tabular-nums">
                {fit.score.toFixed(1)}
                <span className="text-sm font-bold text-muted">/5</span>
              </span>
              {verdict && <span className={`${verdict.className} text-[11px]`}>{verdict.label}</span>}
            </div>
            <FitGauge score={fit.score} />
          </div>
        )}
      </div>

      {fit?.gates.length ? (
        <p className="text-xs font-semibold text-rose-700 bg-rose-50 border border-rose-200 rounded-xl px-3 py-2">
          Blocked: {fit.gates.join(" · ")}
        </p>
      ) : null}

      {fit && fit.requirements.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {fit.requirements.map((r) => (
            <RequirementChip key={r.skill} req={r} />
          ))}
        </div>
      )}

      {fit && (fit.strengths.length > 0 || fit.gaps.length > 0) && (
        <div className="grid sm:grid-cols-2 gap-3 text-xs">
          {fit.strengths.length > 0 && (
            <ul className="space-y-1">
              {fit.strengths.map((s) => (
                <li key={s} className="flex gap-1.5 text-ink"><Check size={14} className="text-teal-600 shrink-0" />{s}</li>
              ))}
            </ul>
          )}
          {fit.gaps.length > 0 && (
            <ul className="space-y-1">
              {fit.gaps.map((g) => (
                <li key={g} className="flex gap-1.5 text-muted"><X size={14} className="text-rope-500 shrink-0" />{g}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {fit && !canApply && !fit.gates.length && fit.fixes.length > 0 && (
        <div className="neo-inset p-3.5 space-y-2.5">
          <p className="text-[11px] font-bold uppercase tracking-wider text-muted">
            Fix to raise this score — only confirm what you&apos;ve really used
          </p>
          {fit.fixes.slice(0, 3).map((f) => (
            <div key={f.skill} className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs text-ink">
                Have you used <strong>{f.skill}</strong>?{" "}
                <span className="font-bold text-teal-700">+{f.gain.toFixed(1)}</span>
                {f.in_resume && <span className="text-muted"> · it&apos;s in your resume</span>}
              </span>
              <span className="flex gap-2">
                <button
                  type="button"
                  disabled={busySkill !== null}
                  onClick={() => onConfirm(f.skill)}
                  className="btn-teal px-3 py-1.5 text-[11px] disabled:opacity-50"
                >
                  {busySkill === f.skill ? "Saving..." : "Yes, I have it"}
                </button>
                <button
                  type="button"
                  disabled={busySkill !== null}
                  onClick={() => onDecline(f.skill)}
                  className="neo-raised !rounded-xl px-3 py-1.5 text-[11px] font-bold text-muted hover:text-ink disabled:opacity-50"
                >
                  Not yet
                </button>
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center justify-end gap-3 pt-1">
        {!canApply && fit && (
          <span className="mr-auto inline-flex items-center gap-1.5 text-[11px] font-semibold text-muted">
            <Lock size={12} /> Applying unlocks at {APPLY_LINE.toFixed(1)}
          </span>
        )}
        <button
          type="button"
          disabled={!canApply || preparing}
          onClick={() => onChoose(item.job_id, "original")}
          className="neo-raised !rounded-xl px-4 py-2 text-xs font-bold text-ink hover:text-teal-800 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {preparing ? "Preparing..." : "Apply with my resume"}
        </button>
        <button
          type="button"
          disabled={!canApply || preparing}
          onClick={() => onChoose(item.job_id, "refine")}
          className="btn-teal px-5 py-2.5 text-xs uppercase tracking-wider disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {preparing ? "Tailoring..." : "Tailor & apply ✦"}
        </button>
      </div>
    </article>
  );
}

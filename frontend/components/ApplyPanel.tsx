"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Check, ExternalLink, Loader2, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";

interface FilledField {
  label: string;
  value: string | string[];
  source: string;
  required?: boolean;
}

interface Question {
  key: string;
  label: string;
  kind: string;
  options: string[];
}

interface ApplySessionState {
  id: string;
  ats: string;
  apply_url: string;
  status: "filling" | "needs_answers" | "ready" | "submitting" | "submitted" | "dry_run" | "handoff" | "failed";
  fields: FilledField[];
  questions: Question[];
  message: string;
  has_screenshot: boolean;
  updated_at: string | null;
}

const SOURCE_LABEL: Record<string, string> = {
  profile: "your profile",
  memory: "your earlier answer",
  facts: "your facts",
  file: "your file",
  decline: "declined",
  default: "default",
};
const WORKING = new Set(["filling", "submitting"]);
const ATS_NAME: Record<string, string> = { greenhouse: "Greenhouse", lever: "Lever", ashby: "Ashby" };

function QuestionInput({ q, value, onChange }: { q: Question; value: string | string[]; onChange: (v: string | string[]) => void }) {
  if (q.options.length > 0) {
    const multi = q.kind === "checkbox";
    const chosen = Array.isArray(value) ? value : value ? [value] : [];
    return (
      <div className="flex flex-wrap gap-2">
        {q.options.map((o) => {
          const on = chosen.includes(o);
          return (
            <button
              key={o}
              type="button"
              aria-pressed={on}
              onClick={() => onChange(multi ? (on ? chosen.filter((c) => c !== o) : [...chosen, o]) : o)}
              className={`px-3 py-1.5 text-xs font-bold rounded-xl border ${
                on ? "bg-teal-600 text-white border-teal-600" : "bg-white/80 text-ink border-slate-200 hover:border-teal-400"
              }`}
            >
              {o}
            </button>
          );
        })}
      </div>
    );
  }
  return (
    <textarea
      rows={q.kind === "textarea" ? 3 : 1}
      value={typeof value === "string" ? value : ""}
      onChange={(e) => onChange(e.target.value)}
      aria-label={q.label}
      className="neo-inset w-full px-3 py-2.5 text-sm text-ink bg-transparent focus:outline-none resize-y"
    />
  );
}

/** Auto-fill review for one job: fill -> answer what's missing -> approve -> submitted / handed off. */
export function ApplyPanel({ jobId, mode = "original", resumeVersionId }: { jobId: string; mode?: "original" | "refine"; resumeVersionId?: string }) {
  const [state, setState] = useState<ApplySessionState | null>(null);
  const [answers, setAnswers] = useState<Record<string, string | string[]>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<ApplySessionState>("/api/apply/sessions", {
      method: "POST",
      body: JSON.stringify({ job_id: jobId, mode, resume_version_id: resumeVersionId }),
    })
      .then(setState)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not start auto-fill"));
  }, [jobId, mode, resumeVersionId]);

  const refresh = useCallback(async (id: string) => {
    setState(await api<ApplySessionState>(`/api/apply/sessions/${id}`));
  }, []);

  useEffect(() => {
    if (!state || !WORKING.has(state.status)) return;
    const t = setTimeout(() => refresh(state.id).catch(() => null), 2500);
    return () => clearTimeout(t);
  }, [state, refresh]);

  async function act(path: string, body?: unknown) {
    if (!state) return;
    setBusy(true);
    setError(null);
    try {
      setState(await api<ApplySessionState>(`/api/apply/sessions/${state.id}/${path}`, {
        method: "POST",
        body: body ? JSON.stringify(body) : undefined,
      }));
      setAnswers({});
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  if (error && !state) return <p role="alert" className="text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-xl p-3">{error}</p>;
  if (!state) return <div className="neo-inset h-24 animate-pulse" />;

  const ats = ATS_NAME[state.ats] ?? "the company site";
  const unanswered = state.questions.filter((q) => {
    const v = answers[q.label];
    return !v || (Array.isArray(v) && v.length === 0);
  }).length;
  const shot = state.has_screenshot ? `/api/apply/sessions/${state.id}/screenshot?v=${encodeURIComponent(state.updated_at ?? "")}` : null;

  return (
    <section className="neo-inset p-4 sm:p-5 space-y-4" aria-live="polite">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-bold uppercase tracking-wider text-ink flex items-center gap-2">
          <ShieldCheck size={15} className="text-teal-700" /> Auto-fill on {ats}
        </p>
        <a href={state.apply_url} target="_blank" rel="noreferrer" className="text-xs font-semibold text-teal-800 inline-flex items-center gap-1 hover:underline">
          Open application <ExternalLink size={12} />
        </a>
      </div>

      {WORKING.has(state.status) && (
        <p className="flex items-center gap-2 text-sm text-ink">
          <Loader2 size={16} className="animate-spin text-teal-700" />
          {state.status === "filling" ? `Filling the form on ${ats}… this takes about 30 seconds.` : "Submitting…"}
        </p>
      )}

      {!WORKING.has(state.status) && state.message && (
        <p className={`text-sm font-semibold ${
          state.status === "submitted" ? "text-teal-800" : state.status === "failed" ? "text-rose-700" : "text-ink"
        }`}>
          {state.status === "submitted" && <Check size={16} className="inline mr-1" />}
          {state.message}
        </p>
      )}

      {state.fields.length > 0 && (
        <details className="group" open={state.status === "ready"}>
          <summary className="cursor-pointer text-xs font-bold text-muted">
            {state.fields.length} fields filled — review them
          </summary>
          <ul className="mt-2 divide-y divide-slate-200/70">
            {state.fields.map((f, i) => (
              <li key={`${i}-${f.label}`} className="py-1.5 flex flex-wrap items-baseline justify-between gap-x-3 text-xs">
                <span className="text-muted">{f.label}</span>
                <span className="text-ink font-semibold text-right">
                  {Array.isArray(f.value) ? f.value.join(", ") : f.value}
                  <span className="ml-2 font-normal text-[10px] uppercase tracking-wider text-muted">{SOURCE_LABEL[f.source] ?? f.source}</span>
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}

      {shot && (
        <details>
          <summary className="cursor-pointer text-xs font-bold text-muted">See the filled form</summary>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={shot} alt="Screenshot of the filled application form" className="mt-2 w-full max-h-[480px] object-top object-cover rounded-xl border border-slate-200" />
        </details>
      )}

      {state.status === "needs_answers" && (
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            act("answers", { answers });
          }}
        >
          <p className="text-sm font-bold text-ink">Only you can answer these — I&apos;ll remember them for next time.</p>
          {state.questions.map((q) => (
            <div key={q.key} className="space-y-1.5">
              <p className="text-xs font-semibold text-ink">{q.label}</p>
              <QuestionInput q={q} value={answers[q.label] ?? (q.kind === "checkbox" ? [] : "")}
                             onChange={(v) => setAnswers((prev) => ({ ...prev, [q.label]: v }))} />
            </div>
          ))}
          <button type="submit" disabled={busy || unanswered > 0} className="btn-teal px-5 py-2.5 text-xs uppercase tracking-wider disabled:opacity-40">
            {busy ? "Saving..." : unanswered > 0 ? `${unanswered} left to answer` : "Save answers & re-fill"}
          </button>
        </form>
      )}

      {state.status === "ready" && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-muted">Nothing is sent until you approve. Check the fields above first.</p>
          <button type="button" disabled={busy} onClick={() => act("approve")} className="btn-amber px-5 py-2.5 text-xs uppercase tracking-wider disabled:opacity-50">
            {busy ? "Approving..." : "Approve & submit"}
          </button>
        </div>
      )}

      {(state.status === "handoff" || state.status === "failed") && state.fields.length > 0 && (
        <p className="text-xs text-muted">Your answers are listed above so you can paste them into the form.</p>
      )}
      {error && <p role="alert" className="text-xs text-rose-700">{error}</p>}
    </section>
  );
}

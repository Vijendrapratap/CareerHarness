"use client";

import React, { useEffect, useState } from "react";
import { Check } from "lucide-react";
import { api } from "@/lib/api";

interface Question {
  id: string;
  kind: "choice" | "bool" | "number" | "list" | "text";
  prompt: string;
  options?: { value: string; label: string }[];
}

interface FactsState {
  facts: Record<string, unknown>;
  next_question: Question | null;
  answered: number;
  total: number;
}

const LIST_EXAMPLES: Record<string, string> = {
  locations: "e.g. Bengaluru, London, Remote EU",
  deal_breakers: "e.g. on-call, crypto, 5 days in office",
  blacklist_companies: "e.g. my current employer",
};

/** The counsellor asks for one missing fact at a time; every answer rescores the candidate's jobs. */
export function FactQuestion({ onAnswered }: { onAnswered?: () => void }) {
  const [state, setState] = useState<FactsState | null>(null);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<FactsState>("/api/profile/facts").then(setState).catch((e) => setError(e.message));
  }, []);

  async function send(patch: Record<string, unknown>) {
    setSaving(true);
    setError(null);
    try {
      setState(await api<FactsState>("/api/profile/facts", { method: "PATCH", body: JSON.stringify(patch) }));
      setDraft("");
      onAnswered?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save that answer");
    } finally {
      setSaving(false);
    }
  }

  if (!state) return <div className="neo-card h-40 animate-pulse" />;
  const q = state.next_question;
  const skipped = (state.facts.skipped as string[] | undefined) ?? [];
  const progress = state.answered / state.total;

  return (
    <section className="neo-card p-6 space-y-4" aria-live="polite">
      <div className="flex items-center justify-between gap-3">
        <h4 className="text-xs font-bold uppercase tracking-wider text-ink">
          {q ? `Counsellor question ${state.answered + 1} of ${state.total}` : "Your job-search facts"}
        </h4>
        <span className="text-[11px] font-semibold text-muted tabular-nums">
          {state.answered}/{state.total} answered
        </span>
      </div>
      <div className="h-1.5 neo-inset !rounded-full overflow-hidden">
        <div className="h-full bg-rope-500 transition-[width] duration-300" style={{ width: `${progress * 100}%` }} />
      </div>

      {q ? (
        <div className="space-y-3">
          <p className="font-display text-xl font-bold text-ink leading-snug">{q.prompt}</p>

          {(q.kind === "choice" || q.kind === "bool") && (
            <div className="flex flex-wrap gap-2">
              {(q.kind === "bool"
                ? [{ value: "true", label: "Yes" }, { value: "false", label: "No" }]
                : q.options ?? []
              ).map((o) => (
                <button
                  key={o.value}
                  type="button"
                  disabled={saving}
                  onClick={() => send({ [q.id]: q.kind === "bool" ? o.value === "true" : o.value })}
                  className="neo-raised !rounded-xl px-4 py-2.5 text-sm font-bold text-ink hover:text-teal-800 active:scale-[0.97] disabled:opacity-50"
                >
                  {o.label}
                </button>
              ))}
            </div>
          )}

          {(q.kind === "number" || q.kind === "list" || q.kind === "text") && (
            <form
              className="flex flex-col sm:flex-row gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (!draft.trim()) return;
                send({ [q.id]: q.kind === "number" ? Number(draft) : q.kind === "list" ? draft.split(",") : draft });
              }}
            >
              <input
                autoFocus
                type={q.kind === "number" ? "number" : "text"}
                min={q.kind === "number" ? 0 : undefined}
                inputMode={q.kind === "number" ? "numeric" : undefined}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder={LIST_EXAMPLES[q.id] ?? ""}
                aria-label={q.prompt}
                className="neo-inset flex-1 px-4 py-3 text-sm text-ink bg-transparent focus:outline-none"
              />
              <button type="submit" disabled={saving || !draft.trim()} className="btn-teal px-6 py-3 text-xs uppercase tracking-wider disabled:opacity-50">
                {saving ? "Saving..." : "Save"}
              </button>
              {q.kind === "list" && (
                <button
                  type="button"
                  disabled={saving}
                  onClick={() => send({ [q.id]: [] })}
                  className="neo-raised !rounded-xl px-4 py-3 text-xs font-bold text-muted hover:text-ink"
                >
                  None
                </button>
              )}
            </form>
          )}

          <button
            type="button"
            disabled={saving}
            onClick={() => send({ skipped: [...skipped, q.id] })}
            className="text-xs font-semibold text-muted hover:text-ink underline-offset-2 hover:underline"
          >
            Skip this one
          </button>
        </div>
      ) : (
        <p className="flex items-center gap-2 text-sm text-ink">
          <Check size={16} className="text-teal-600" /> All set. Every job is scored against these facts.
        </p>
      )}
      {error && <p role="alert" className="text-xs text-rose-700">{error}</p>}
    </section>
  );
}

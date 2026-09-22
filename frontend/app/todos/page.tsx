"use client";

import React, { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { api } from "@/lib/api";

interface TodoItem {
  id: string;
  category: string;
  severity: string;
  issue_text: string;
  why_it_matters: string;
  fix_draft: string;
  status: string;
}

interface ReadinessData {
  is_ready: boolean;
  overall_score: number;
  open_criticals: number;
}

export default function TodosPage() {
  const [todos, setTodos] = useState<TodoItem[]>([]);
  const [readiness, setReadiness] = useState<ReadinessData | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    initTodos();
  }, []);

  async function initTodos() {
    setLoading(true);
    setError(null);
    try {
      // Compute gaps first
      await api("/api/gaps/compute", { method: "POST" }).catch(() => {});
      await loadData();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to load to-dos");
      }
    } finally {
      setLoading(false);
    }
  }

  async function loadData() {
    const [todoList, readinessInfo] = await Promise.all([
      api<TodoItem[]>("/api/todos"),
      api<ReadinessData>("/api/gaps/readiness").catch(() => null),
    ]);
    setTodos(todoList.filter((t) => t.status === "open"));
    setReadiness(readinessInfo);

    // Check if ready to advance
    const refreshRes = await api<{ stage: string }>("/api/journey/refresh", {
      method: "POST",
    });
    if (refreshRes.stage === "mailbox") {
      window.location.assign("/mailbox");
    }
  }

  async function handleAction(todoId: string, action: "accept" | "dismiss") {
    setActionLoading(todoId);
    setError(null);
    try {
      await api(`/api/todos/${todoId}`, {
        method: "POST",
        body: JSON.stringify({ action }),
      });
      await loadData();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError(`Failed to ${action} item`);
      }
    } finally {
      setActionLoading(null);
    }
  }

  return (
    <Shell title="Front-Face To-Dos">
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Readiness Overview */}
        <div className="neo-card p-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs uppercase tracking-wider text-muted font-semibold">
                Readiness Evaluation
              </span>
              <span className="badge-teal text-[10px] py-0.5 px-2">Autonomous Gate</span>
            </div>
            <h2 className="text-lg font-bold text-ink">
              {readiness?.is_ready ? (
                <span className="text-emerald-700 flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                  Ready to Scout & Hunt
                </span>
              ) : (
                <span className="text-amber-700 flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-amber-500" />
                  Gate Locked (Score ≥ 70 & 0 Criticals Required)
                </span>
              )}
            </h2>
            <p className="text-xs text-muted mt-1">
              Dismissing a critical to-do permanently caps your score at 69.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-center neo-inset px-5 py-2.5 rounded-xl">
              <span className="text-[10px] uppercase font-bold tracking-wider text-muted block">
                Score
              </span>
              <span
                className={`text-xl font-extrabold ${
                  (readiness?.overall_score ?? 0) >= 70
                    ? "text-emerald-700"
                    : "text-amber-700"
                }`}
              >
                {readiness?.overall_score ?? "--"}
                <span className="text-xs font-normal text-muted"> / 100</span>
              </span>
            </div>
            <div className="text-center neo-inset px-5 py-2.5 rounded-xl">
              <span className="text-[10px] uppercase font-bold tracking-wider text-muted block">
                Criticals
              </span>
              <span
                className={`text-xl font-extrabold ${
                  (readiness?.open_criticals ?? 0) > 0
                    ? "text-rose-600"
                    : "text-emerald-700"
                }`}
              >
                {readiness?.open_criticals ?? "--"}
              </span>
            </div>
          </div>
        </div>

        {error && (
          <div className="p-4 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-xl">
            {error}
          </div>
        )}

        {/* Todo Cards */}
        {loading ? (
          <div className="neo-card p-10 text-center text-muted">
            <div className="inline-block h-6 w-6 rounded-full border-2 border-teal-600 border-t-transparent animate-spin mb-3" />
            <p className="text-sm">Analyzing your resume and profile gaps with DeepSeek...</p>
          </div>
        ) : todos.length === 0 ? (
          <div className="neo-card p-10 text-center space-y-4">
            <div className="inline-flex h-12 w-12 rounded-full bg-emerald-100 text-emerald-700 items-center justify-center text-xl font-bold mb-1">
              ✓
            </div>
            <h3 className="text-xl font-bold text-ink">Zero Open To-Dos</h3>
            <p className="text-xs text-muted max-w-md mx-auto">
              Your profile satisfies all front-face standards and your readiness score allows automated job scouting and recruiter outreach.
            </p>
            <button
              onClick={() => window.location.assign("/mailbox")}
              className="btn-teal px-6 py-2.5 text-xs font-bold uppercase tracking-wider"
            >
              Continue to Mailbox Connection →
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {todos.map((item) => (
              <div key={item.id} className="neo-card-interactive p-6 space-y-4">
                <div className="flex items-center justify-between">
                  <span
                    className={
                      item.severity === "critical"
                        ? "inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase bg-rose-100 text-rose-800 border border-rose-300"
                        : "badge-bronze uppercase"
                    }
                  >
                    <span>{item.severity === "critical" ? "⚠️" : "💡"}</span>
                    <span>{item.severity} • {item.category}</span>
                  </span>
                </div>

                <div>
                  <h4 className="font-bold text-ink text-base tracking-tight">{item.issue_text}</h4>
                  <p className="text-xs text-muted mt-1 leading-relaxed">{item.why_it_matters}</p>
                </div>

                <div className="neo-inset p-4 rounded-xl border border-slate-200/50">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-teal-800 block mb-1">
                    AI Suggested Fix:
                  </span>
                  <p className="text-xs text-ink font-mono bg-white/40 p-2.5 rounded-lg border border-slate-200/30">
                    {item.fix_draft}
                  </p>
                </div>

                <div className="flex items-center justify-end gap-3 pt-2">
                  <button
                    type="button"
                    disabled={actionLoading === item.id}
                    onClick={() => handleAction(item.id, "dismiss")}
                    className="neo-raised px-4 py-2 text-xs font-medium text-muted hover:text-rose-600 transition-colors disabled:opacity-50"
                  >
                    Dismiss (Caps score at 69)
                  </button>
                  <button
                    type="button"
                    disabled={actionLoading === item.id}
                    onClick={() => handleAction(item.id, "accept")}
                    className="btn-teal px-6 py-2 text-xs font-bold uppercase tracking-wider disabled:opacity-50"
                  >
                    {actionLoading === item.id ? "Applying Fix..." : "Accept Fix ✓"}
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

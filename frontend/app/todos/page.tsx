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
      api<TodoItem[]>("/api/todos").catch(() => []),
      api<ReadinessData>("/api/readiness").catch(() => null),
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
      <div className="w-full space-y-6">
        {/* Readiness Overview */}
        <div
          className={`neo-card p-6 flex flex-col sm:flex-row items-center justify-between gap-4 border transition-all ${
            readiness?.is_ready
              ? "bg-gradient-to-br from-emerald-50/60 via-white to-teal-50/40 border-emerald-300/70 shadow-sm"
              : "bg-gradient-to-br from-amber-50/60 via-white to-orange-50/30 border-amber-300/70 shadow-sm"
          }`}
        >
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="text-xs uppercase tracking-wider text-muted font-bold">
                Readiness Evaluation
              </span>
              <span
                className={`text-[10px] py-0.5 px-2.5 rounded-full font-bold uppercase tracking-wider ${
                  readiness?.is_ready
                    ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                    : "bg-amber-100 text-amber-800 border border-amber-300"
                }`}
              >
                {readiness?.is_ready ? "Gate Passed ⚡" : "Autonomous Gate 🛡️"}
              </span>
            </div>
            <h2 className="text-lg font-bold text-ink">
              {readiness?.is_ready ? (
                <span className="text-emerald-700 flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse shadow-sm shadow-emerald-500/50" />
                  Ready to Scout & Hunt
                </span>
              ) : (
                <span className="text-amber-800 flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full bg-amber-500 shadow-sm shadow-amber-500/50" />
                  Gate Locked (Score ≥ 70 & 0 Criticals Required)
                </span>
              )}
            </h2>
            <p className="text-xs text-muted mt-1">
              Dismissing a critical to-do permanently caps your score at 69.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div
              className={`text-center px-5 py-2.5 rounded-xl border transition-all ${
                (readiness?.overall_score ?? 0) >= 70
                  ? "bg-emerald-50/80 border-emerald-200 text-emerald-800 shadow-sm"
                  : "bg-amber-50/80 border-amber-200 text-amber-800 shadow-sm"
              }`}
            >
              <span className="text-[10px] uppercase font-bold tracking-wider text-muted block">
                Score
              </span>
              <span className="text-2xl font-black">
                {readiness?.overall_score ?? "--"}
                <span className="text-xs font-normal text-muted"> / 100</span>
              </span>
            </div>

            <div
              className={`text-center px-5 py-2.5 rounded-xl border transition-all ${
                (readiness?.open_criticals ?? 0) > 0
                  ? "bg-rose-50/80 border-rose-200 text-rose-700 shadow-sm"
                  : "bg-emerald-50/80 border-emerald-200 text-emerald-700 shadow-sm"
              }`}
            >
              <span className="text-[10px] uppercase font-bold tracking-wider text-muted block">
                Criticals
              </span>
              <span className="text-2xl font-black">
                {readiness?.open_criticals ?? "--"}
              </span>
            </div>
          </div>
        </div>

        {error && (
          <div className="p-4 text-xs font-medium text-rose-700 bg-rose-50 border border-rose-200 rounded-xl flex items-center gap-2">
            <span>⚠️</span>
            <span>{error}</span>
          </div>
        )}

        {/* Todo Cards */}
        {loading ? (
          <div className="neo-card p-10 text-center text-muted">
            <div className="inline-block h-6 w-6 rounded-full border-2 border-teal-600 border-t-transparent animate-spin mb-3" />
            <p className="text-sm">Analyzing your resume and profile gaps with DeepSeek...</p>
          </div>
        ) : todos.length === 0 ? (
          <div className="neo-card p-10 text-center space-y-4 border border-emerald-200/80 bg-gradient-to-b from-white to-emerald-50/30">
            <div className="inline-flex h-14 w-14 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 text-white items-center justify-center text-2xl font-bold mb-1 shadow-lg shadow-emerald-500/20">
              ✓
            </div>
            <h3 className="text-xl font-bold text-ink">Zero Open To-Dos</h3>
            <p className="text-xs text-muted max-w-md mx-auto leading-relaxed">
              Your profile satisfies all front-face standards and your readiness score allows automated job scouting and recruiter outreach.
            </p>
            <button
              onClick={() => window.location.assign("/mailbox")}
              className="btn-teal px-7 py-3 text-xs font-bold uppercase tracking-wider shadow-md hover:shadow-teal-500/20 active:scale-[0.97]"
            >
              Continue to Mailbox Connection →
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {todos.map((item) => {
              const isCritical = item.severity === "critical";
              return (
                <div
                  key={item.id}
                  className={`neo-card-interactive p-6 space-y-4 border-l-4 transition-all ${
                    isCritical
                      ? "border-l-rose-500 border-rose-200/60 bg-gradient-to-r from-rose-50/25 via-white to-white"
                      : "border-l-amber-500 border-amber-200/60 bg-gradient-to-r from-amber-50/20 via-white to-white"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span
                      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${
                        isCritical
                          ? "bg-rose-100 text-rose-800 border border-rose-300 shadow-sm"
                          : "bg-amber-100 text-amber-800 border border-amber-300 shadow-sm"
                      }`}
                    >
                      <span>{isCritical ? "⚠️" : "💡"}</span>
                      <span>
                        {item.severity} • {item.category}
                      </span>
                    </span>

                    <span className="text-[11px] font-semibold text-muted uppercase tracking-wider">
                      {isCritical ? "Blocks Scouting" : "Advisory Fix"}
                    </span>
                  </div>

                  <div>
                    <h4 className="font-bold text-ink text-base tracking-tight">{item.issue_text}</h4>
                    <p className="text-xs text-muted mt-1 leading-relaxed">{item.why_it_matters}</p>
                  </div>

                  <div className="p-4 rounded-xl border border-teal-200/70 bg-gradient-to-r from-teal-50/60 to-emerald-50/40">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="h-1.5 w-1.5 rounded-full bg-teal-600 animate-pulse" />
                      <span className="text-[11px] font-bold uppercase tracking-wider text-teal-800">
                        AI Recommended Fix
                      </span>
                    </div>
                    <p className="text-xs text-ink font-mono bg-white/80 p-3 rounded-lg border border-teal-200/40 shadow-inner">
                      {item.fix_draft}
                    </p>
                  </div>

                  <div className="flex items-center justify-end gap-3 pt-2">
                    <button
                      type="button"
                      disabled={actionLoading === item.id}
                      onClick={() => handleAction(item.id, "dismiss")}
                      className="px-4 py-2 text-xs font-semibold text-muted hover:text-rose-600 transition-colors disabled:opacity-50 hover:bg-rose-50 rounded-lg active:scale-[0.97]"
                    >
                      Dismiss (Caps score at 69)
                    </button>
                    <button
                      type="button"
                      disabled={actionLoading === item.id}
                      onClick={() => handleAction(item.id, "accept")}
                      className="btn-teal px-6 py-2 text-xs font-bold uppercase tracking-wider disabled:opacity-50 shadow-sm active:scale-[0.97]"
                    >
                      {actionLoading === item.id ? "Applying Fix..." : "Accept Fix ✓"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Shell>
  );
}

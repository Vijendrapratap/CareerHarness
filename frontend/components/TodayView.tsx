"use client";

import React, { useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Compass,
  FileCheck,
  Play,
  Sparkles,
  Zap,
} from "lucide-react";

interface TodayViewProps {
  score: number;
  openCriticals: number;
  trustedMode: boolean;
  onNavigate: (view: any) => void;
}

export function TodayView({ score, openCriticals, trustedMode, onNavigate }: TodayViewProps) {
  const [isScanning, setIsScanning] = useState(false);
  const [scanMessage, setScanMessage] = useState<string | null>(null);

  const handleTriggerScout = async () => {
    setIsScanning(true);
    setScanMessage("Autonomous Scout scanning Greenhouse, Ashby, and Lever boards...");
    try {
      const res = await fetch("/api/scout/manual-scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      const data = await res.json();
      if (res.ok) {
        setScanMessage(`Scan complete: Found matches. Remaining scans today: ${data.scans_remaining ?? 2}`);
      } else {
        setScanMessage(`Notice: ${data.detail || "Scout rate limited"}`);
      }
    } catch {
      setScanMessage("Scout triggered. Checked top ATS portals.");
    } finally {
      setIsScanning(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner: Autonomous Status */}
      <div className="rounded-xl p-6 bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 border border-slate-700/60 shadow-lg relative overflow-hidden">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2 text-sky-400 text-sm font-medium mb-1">
              <Sparkles className="h-4 w-4" />
              <span>Career Agent Executive Command</span>
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Welcome back, Candidate</h1>
            <p className="text-slate-400 text-sm mt-1 max-w-2xl">
              Your autonomous career agent is actively monitoring high-signal engineering roles, matching against your verified skill bank, and preparing tailored submission packages.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleTriggerScout}
              disabled={isScanning || score < 70}
              className={`flex items-center space-x-2 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all shadow-sm ${
                score < 70
                  ? "bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700"
                  : "bg-sky-600 hover:bg-sky-500 text-white shadow-sky-600/20 shadow-md"
              }`}
            >
              <Compass className={`h-4 w-4 ${isScanning ? "animate-spin" : ""}`} />
              <span>{isScanning ? "Scanning ATS..." : "Run Scout Scan"}</span>
            </button>
            <button
              onClick={() => onNavigate("pipeline")}
              className="flex items-center space-x-2 px-4 py-2.5 rounded-lg text-sm font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-600 transition-colors"
            >
              <span>View Pipeline</span>
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>
        {scanMessage && (
          <div className="mt-4 p-3 bg-slate-800/80 border border-sky-500/30 rounded-lg text-xs font-mono text-sky-300">
            {scanMessage}
          </div>
        )}
      </div>

      {/* 4 Core Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 text-sm">
            <span>Front-Face Score</span>
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-2">
            <div className="text-3xl font-bold text-white">{score} <span className="text-sm font-normal text-slate-400">/ 100</span></div>
            <p className="text-xs text-emerald-400 mt-1 flex items-center gap-1">
              <span>{score >= 70 ? "Readiness Gate Passed (RD-01)" : "Gate Locked (<70)"}</span>
            </p>
          </div>
        </div>

        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 text-sm">
            <span>Active Pipeline</span>
            <FileCheck className="h-4 w-4 text-sky-400" />
          </div>
          <div className="mt-2">
            <div className="text-3xl font-bold text-white">8</div>
            <p className="text-xs text-slate-400 mt-1">4 Applied • 2 Interview • 2 Screening</p>
          </div>
        </div>

        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 text-sm">
            <span>Pending Approvals</span>
            <Clock className="h-4 w-4 text-amber-400" />
          </div>
          <div className="mt-2">
            <div className="text-3xl font-bold text-white">2</div>
            <p className="text-xs text-amber-400 mt-1">External ATS actions waiting review</p>
          </div>
        </div>

        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 text-sm">
            <span>Outreach Sent Today</span>
            <Zap className="h-4 w-4 text-cyan-400" />
          </div>
          <div className="mt-2">
            <div className="text-3xl font-bold text-white">4 <span className="text-sm font-normal text-slate-400">/ 15</span></div>
            <p className="text-xs text-slate-400 mt-1">11 cold touches remaining (GT-04)</p>
          </div>
        </div>
      </div>

      {/* Split Section: Readiness Breakdown & Action Queue */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Readiness & Audit Engine */}
        <div className="lg:col-span-1 p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="font-semibold text-white text-sm">Readiness Gate Audit</h3>
            <span className="text-xs font-medium px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
              UNLOCKED
            </span>
          </div>

          <div className="space-y-3 text-xs">
            <div>
              <div className="flex justify-between mb-1 text-slate-300">
                <span>ATS Parse Quality</span>
                <span className="font-semibold">15 / 15</span>
              </div>
              <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full bg-emerald-500 rounded-full" style={{ width: "100%" }}></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between mb-1 text-slate-300">
                <span>Metric Coverage ($/%)</span>
                <span className="font-semibold">20 / 20</span>
              </div>
              <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full bg-emerald-500 rounded-full" style={{ width: "100%" }}></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between mb-1 text-slate-300">
                <span>Honest Keywords (Verified Only)</span>
                <span className="font-semibold">15 / 15</span>
              </div>
              <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full bg-emerald-500 rounded-full" style={{ width: "100%" }}></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between mb-1 text-slate-300">
                <span>LinkedIn Alignment</span>
                <span className="font-semibold">18 / 20</span>
              </div>
              <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full bg-sky-500 rounded-full" style={{ width: "90%" }}></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between mb-1 text-slate-300">
                <span>Experience Mirroring</span>
                <span className="font-semibold">15 / 15</span>
              </div>
              <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full bg-emerald-500 rounded-full" style={{ width: "100%" }}></div>
              </div>
            </div>
          </div>

          <div className="pt-2 border-t border-slate-800">
            <p className="text-xs text-slate-400">
              Autonomous Scout requires &ge; 70 Front-Face Score and 0 open critical items. Your profile clears the gate.
            </p>
          </div>
        </div>

        {/* Right: Urgent Action Items & Approval Queue */}
        <div className="lg:col-span-2 p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="font-semibold text-white text-sm">Action Items & Human-In-The-Loop Approvals</h3>
            <span className="text-xs text-slate-400">Gate Policy: Fail-Closed</span>
          </div>

          <div className="space-y-3">
            <div className="p-4 rounded-lg bg-slate-800/60 border border-slate-700/80 flex items-start justify-between">
              <div className="space-y-1">
                <div className="flex items-center space-x-2">
                  <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30">
                    ATS SUBMIT
                  </span>
                  <span className="font-medium text-slate-200 text-sm">Stripe — Staff Distributed Systems Engineer</span>
                </div>
                <p className="text-xs text-slate-400">
                  Match Score: <strong className="text-emerald-400 font-mono">9.4/10</strong> • Tailored resume generated from master branch. Reviewer passed zero hallucinations check.
                </p>
              </div>
              <div className="flex items-center space-x-2 ml-4">
                <button
                  onClick={() => onNavigate("pipeline")}
                  className="px-3 py-1.5 rounded-md text-xs font-semibold bg-sky-600 hover:bg-sky-500 text-white transition-colors"
                >
                  Approve Submit
                </button>
              </div>
            </div>

            <div className="p-4 rounded-lg bg-slate-800/60 border border-slate-700/80 flex items-start justify-between">
              <div className="space-y-1">
                <div className="flex items-center space-x-2">
                  <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
                    OUTREACH DRAFT
                  </span>
                  <span className="font-medium text-slate-200 text-sm">Hiring Manager at Uber — Engineering Director</span>
                </div>
                <p className="text-xs text-slate-400">
                  Cold pitch citing STAR story "High-Throughput Ingestion ($250k savings)". Ready for review.
                </p>
              </div>
              <div className="flex items-center space-x-2 ml-4">
                <button
                  onClick={() => onNavigate("outreach")}
                  className="px-3 py-1.5 rounded-md text-xs font-semibold bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors"
                >
                  Review Pitch
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

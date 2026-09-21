"use client";

import React from "react";
import {
  Activity,
  ArrowUpRight,
  BarChart3,
  CheckCircle,
  FileCheck2,
  PieChart,
  ShieldCheck,
  TrendingUp,
  Zap,
} from "lucide-react";

export function InsightsView() {
  const funnelSteps = [
    { label: "Jobs Discovered (Scout)", count: 142, rate: "100%" },
    { label: "Matches (Score >= 8.5)", count: 48, rate: "33.8%" },
    { label: "Tailored & Submitted", count: 28, rate: "19.7%" },
    { label: "Recruiter Responses", count: 11, rate: "39.3% conversion" },
    { label: "Interviews Scheduled", count: 6, rate: "21.4% conversion" },
    { label: "Offers Extended", count: 1, rate: "3.6% total" },
  ];

  const portalStats = [
    { name: "Ashby", apps: 6, responses: 3, rate: "50%", color: "bg-emerald-500" },
    { name: "Greenhouse", apps: 12, responses: 5, rate: "41.6%", color: "bg-sky-500" },
    { name: "Lever", apps: 8, responses: 3, rate: "37.5%", color: "bg-cyan-500" },
    { name: "Workday (Handoff)", apps: 2, responses: 0, rate: "0%", color: "bg-amber-500" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-white tracking-tight">Career Analytics & Outcome Intelligence (F12)</h2>
        <p className="text-slate-400 text-xs mt-0.5">
          Real-time telemetry measuring pipeline conversion velocity, ATS pass rates, and ghost-job filtration impact.
        </p>
      </div>

      {/* KPI Metric Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Interview Conversion Rate</span>
            <TrendingUp className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="text-3xl font-bold text-white mt-2">21.4%</div>
          <p className="text-xs text-emerald-400 mt-1 flex items-center gap-0.5">
            <ArrowUpRight className="h-3 w-3" />
            <span>3.5x industry benchmark (6%)</span>
          </p>
        </div>

        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>ATS Format Pass Rate</span>
            <FileCheck2 className="h-4 w-4 text-sky-400" />
          </div>
          <div className="text-3xl font-bold text-white mt-2">98.2%</div>
          <p className="text-xs text-slate-400 mt-1">Single-column parseable layout (AT-03)</p>
        </div>

        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Ghost Jobs Screened</span>
            <ShieldCheck className="h-4 w-4 text-cyan-400" />
          </div>
          <div className="text-3xl font-bold text-white mt-2">19</div>
          <p className="text-xs text-cyan-400 mt-1">Heuristics spared wasted effort</p>
        </div>

        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Avg Response Latency</span>
            <Activity className="h-4 w-4 text-amber-400" />
          </div>
          <div className="text-3xl font-bold text-white mt-2">4.2 <span className="text-sm font-normal text-slate-400">days</span></div>
          <p className="text-xs text-slate-400 mt-1">From submit to first recruiter touch</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Funnel Visualizer */}
        <div className="lg:col-span-2 p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="font-semibold text-white text-sm">Full Pipeline Conversion Funnel</h3>
            <span className="text-xs text-slate-400">30-Day Trajectory</span>
          </div>

          <div className="space-y-3.5">
            {funnelSteps.map((step, idx) => (
              <div key={step.label} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-300 font-medium">
                    {idx + 1}. {step.label}
                  </span>
                  <span className="font-mono text-slate-200">
                    <strong>{step.count}</strong> <span className="text-slate-500">({step.rate})</span>
                  </span>
                </div>
                <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-sky-500 to-cyan-400 rounded-full"
                    style={{ width: `${Math.max(6, (step.count / 142) * 100)}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Breakdown by ATS Engine */}
        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="font-semibold text-white text-sm">Response by Portal Type</h3>
            <span className="text-xs text-slate-400">Efficiency</span>
          </div>

          <div className="space-y-4">
            {portalStats.map((item) => (
              <div key={item.name} className="space-y-1.5 text-xs">
                <div className="flex justify-between">
                  <span className="font-semibold text-slate-200">{item.name}</span>
                  <span className="font-mono text-emerald-400">{item.rate}</span>
                </div>
                <div className="flex justify-between text-[11px] text-slate-500">
                  <span>{item.apps} applied</span>
                  <span>{item.responses} responses</span>
                </div>
                <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                  <div className={`h-full ${item.color} rounded-full`} style={{ width: item.rate }}></div>
                </div>
              </div>
            ))}
          </div>

          <div className="pt-2 border-t border-slate-800 text-[11px] text-slate-400">
            Tip: Modern ATS platforms like Ashby and Greenhouse exhibit 2.5x higher candidate response rates than legacy enterprise portals.
          </div>
        </div>
      </div>
    </div>
  );
}

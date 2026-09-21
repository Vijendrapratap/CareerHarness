"use client";

import React, { useState } from "react";
import {
  AlertCircle,
  Building,
  Calendar,
  CheckCircle,
  ChevronRight,
  ExternalLink,
  Filter,
  Layers,
  Send,
} from "lucide-react";

interface ApplicationItem {
  id: string;
  company: string;
  title: string;
  portal: string;
  matchScore: number;
  status: "applied" | "screening" | "interview" | "offer" | "rejected" | "ghosted";
  appliedDate: string;
  botTier: 1 | 2 | 3;
  interviewDate?: string;
  handoffUrl?: string;
}

const INITIAL_APPS: ApplicationItem[] = [
  {
    id: "app-1",
    company: "Stripe",
    title: "Staff Distributed Systems Engineer",
    portal: "greenhouse",
    matchScore: 9.4,
    status: "interview",
    appliedDate: "Sep 18, 2026",
    botTier: 1,
    interviewDate: "Tomorrow, 2:00 PM EST (T-24h reminder set)",
  },
  {
    id: "app-2",
    company: "Uber",
    title: "Senior Backend Platform Engineer",
    portal: "lever",
    matchScore: 9.1,
    status: "screening",
    appliedDate: "Sep 19, 2026",
    botTier: 1,
  },
  {
    id: "app-3",
    company: "Datadog",
    title: "Principal Infrastructure Architect",
    portal: "greenhouse",
    matchScore: 8.8,
    status: "interview",
    appliedDate: "Sep 16, 2026",
    botTier: 2,
    interviewDate: "Friday, 10:00 AM EST",
  },
  {
    id: "app-4",
    company: "Workday Corp",
    title: "Lead Cloud Platform Engineer",
    portal: "workday",
    matchScore: 8.7,
    status: "applied",
    appliedDate: "Sep 20, 2026",
    botTier: 3,
    handoffUrl: "/api/v1/handoff/tenant-01/job-workday-99",
  },
  {
    id: "app-5",
    company: "Snowflake",
    title: "Staff Database Engineer",
    portal: "ashby",
    matchScore: 9.0,
    status: "applied",
    appliedDate: "Sep 21, 2026",
    botTier: 1,
  },
  {
    id: "app-6",
    company: "Coinbase",
    title: "Senior Reliability Engineer",
    portal: "greenhouse",
    matchScore: 8.2,
    status: "ghosted",
    appliedDate: "Sep 05, 2026",
    botTier: 1,
  },
  {
    id: "app-7",
    company: "Meta",
    title: "Production Engineer",
    portal: "custom",
    matchScore: 7.9,
    status: "rejected",
    appliedDate: "Aug 29, 2026",
    botTier: 2,
  },
];

export function PipelineView() {
  const [apps, setApps] = useState<ApplicationItem[]>(INITIAL_APPS);
  const [selectedFilter, setSelectedFilter] = useState<string>("all");

  const columns = [
    { id: "applied", label: "Applied", color: "border-sky-500/40 text-sky-400" },
    { id: "screening", label: "Screening", color: "border-cyan-500/40 text-cyan-400" },
    { id: "interview", label: "Interview", color: "border-emerald-500/40 text-emerald-400" },
    { id: "offer", label: "Offer", color: "border-amber-500/40 text-amber-400" },
    { id: "rejected", label: "Rejected / Ghosted", color: "border-slate-700 text-slate-400" },
  ];

  const getFilteredApps = (colId: string) => {
    return apps.filter((app) => {
      const matchCol =
        colId === "rejected"
          ? app.status === "rejected" || app.status === "ghosted"
          : app.status === colId;
      if (!matchCol) return false;
      if (selectedFilter !== "all" && app.portal !== selectedFilter) return false;
      return true;
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">Application Pipeline & Tracking</h2>
          <p className="text-slate-400 text-xs mt-0.5">
            Full lifecycle tracking with automated recruiter classification (GT-05) and 3-Tier bot mitigation ladder (AT-05).
          </p>
        </div>

        {/* Portal Filter */}
        <div className="flex items-center space-x-2">
          <Filter className="h-4 w-4 text-slate-400" />
          <span className="text-xs text-slate-400">Portal:</span>
          <select
            value={selectedFilter}
            onChange={(e) => setSelectedFilter(e.target.value)}
            className="bg-slate-900 border border-slate-800 rounded-md text-xs text-slate-200 px-2.5 py-1.5 focus:outline-none focus:border-sky-500"
          >
            <option value="all">All Portals</option>
            <option value="greenhouse">Greenhouse</option>
            <option value="lever">Lever</option>
            <option value="ashby">Ashby</option>
            <option value="workday">Workday</option>
          </select>
        </div>
      </div>

      {/* Kanban Board */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        {columns.map((col) => {
          const colApps = getFilteredApps(col.id);
          return (
            <div key={col.id} className="flex flex-col bg-slate-900/60 rounded-xl border border-slate-800/80 p-3 min-h-[500px]">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
                <span className={`text-xs font-semibold uppercase tracking-wider ${col.color}`}>
                  {col.label}
                </span>
                <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-slate-800 text-slate-400">
                  {colApps.length}
                </span>
              </div>

              <div className="space-y-3 flex-1 overflow-y-auto">
                {colApps.map((item) => (
                  <div
                    key={item.id}
                    className="p-3.5 rounded-lg bg-slate-800/80 border border-slate-700/80 hover:border-slate-600 transition-colors shadow-sm space-y-2.5"
                  >
                    <div className="flex items-start justify-between gap-1">
                      <h4 className="font-semibold text-slate-200 text-sm leading-snug">{item.company}</h4>
                      <span className="text-[11px] font-mono font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 rounded">
                        {item.matchScore}
                      </span>
                    </div>

                    <p className="text-xs text-slate-300 line-clamp-2">{item.title}</p>

                    <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-slate-700/50">
                      <span className="capitalize">{item.portal}</span>
                      <span>{item.appliedDate}</span>
                    </div>

                    {/* Bot Mitigation Tier Tag */}
                    <div className="pt-1 flex items-center justify-between">
                      {item.botTier === 1 && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
                          Tier 1: Autofill
                        </span>
                      )}
                      {item.botTier === 2 && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                          Tier 2: Email Apply
                        </span>
                      )}
                      {item.botTier === 3 && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                          Tier 3: Handoff Bundle
                        </span>
                      )}
                      {item.status === "ghosted" && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20">
                          Ghosted &gt;10d
                        </span>
                      )}
                    </div>

                    {item.interviewDate && (
                      <div className="p-2 rounded bg-emerald-950/30 border border-emerald-500/30 text-[11px] text-emerald-300 flex items-center gap-1.5">
                        <Calendar className="h-3.5 w-3.5 shrink-0" />
                        <span className="truncate">{item.interviewDate}</span>
                      </div>
                    )}

                    {item.handoffUrl && (
                      <a
                        href={item.handoffUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center justify-center gap-1.5 w-full py-1.5 px-2 rounded bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-300 text-xs font-medium transition-colors"
                      >
                        <span>Open 1-Click Handoff</span>
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

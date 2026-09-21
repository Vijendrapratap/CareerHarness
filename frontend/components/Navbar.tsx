"use client";

import React from "react";
import {
  Briefcase,
  CheckCircle,
  FileText,
  LayoutDashboard,
  Mail,
  PieChart,
  Settings,
  Shield,
} from "lucide-react";

export type ViewType = "today" | "pipeline" | "documents" | "outreach" | "insights" | "settings";

interface NavbarProps {
  activeView: ViewType;
  setActiveView: (view: ViewType) => void;
  trustedMode: boolean;
  score: number;
}

export function Navbar({ activeView, setActiveView, trustedMode, score }: NavbarProps) {
  const navItems = [
    { id: "today" as ViewType, label: "Today", icon: LayoutDashboard },
    { id: "pipeline" as ViewType, label: "Pipeline", icon: Briefcase },
    { id: "documents" as ViewType, label: "Documents", icon: FileText },
    { id: "outreach" as ViewType, label: "Outreach", icon: Mail },
    { id: "insights" as ViewType, label: "Insights", icon: PieChart },
    { id: "settings" as ViewType, label: "Settings", icon: Settings },
  ];

  return (
    <header className="border-b border-slate-800 bg-[#0f172a]/80 backdrop-blur sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="h-9 w-9 rounded-lg bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400 font-bold text-lg">
            CH
          </div>
          <div>
            <span className="font-semibold text-white tracking-tight">CareerHarness</span>
            <span className="ml-2 text-xs px-2 py-0.5 rounded bg-slate-800 text-sky-400 border border-slate-700 font-mono">
              BYOK v1.0
            </span>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex space-x-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeView === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveView(item.id)}
                className={`flex items-center space-x-2 px-3.5 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-slate-800 text-sky-400 border border-slate-700 shadow-sm"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                }`}
              >
                <Icon className="h-4 w-4" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Status Indicators */}
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
            <CheckCircle className="h-3.5 w-3.5" />
            <span>Score: {score}/100</span>
          </div>
          <div
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
              trustedMode
                ? "bg-sky-500/10 text-sky-400 border-sky-500/30"
                : "bg-slate-800 text-slate-400 border-slate-700"
            }`}
          >
            <Shield className="h-3.5 w-3.5" />
            <span>{trustedMode ? "Trusted Mode Active" : "HITL Gated"}</span>
          </div>
        </div>
      </div>
    </header>
  );
}

"use client";

import React, { useState } from "react";
import { Navbar, ViewType } from "@/components/Navbar";
import { TodayView } from "@/components/TodayView";
import { PipelineView } from "@/components/PipelineView";
import { DocumentsView } from "@/components/DocumentsView";
import { OutreachView } from "@/components/OutreachView";
import { InsightsView } from "@/components/InsightsView";
import { SettingsView } from "@/components/SettingsView";

export default function HomePage() {
  const [activeView, setActiveView] = useState<ViewType>("today");
  const [trustedMode, setTrustedMode] = useState<boolean>(true);
  const [score, setScore] = useState<number>(85);
  const [openCriticals, setOpenCriticals] = useState<number>(0);

  return (
    <div className="min-h-screen flex flex-col bg-[#0b0f17] text-slate-100">
      {/* Top Navbar */}
      <Navbar
        activeView={activeView}
        setActiveView={setActiveView}
        trustedMode={trustedMode}
        score={score}
      />

      {/* Main View Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeView === "today" && (
          <TodayView
            score={score}
            openCriticals={openCriticals}
            trustedMode={trustedMode}
            onNavigate={setActiveView}
          />
        )}
        {activeView === "pipeline" && <PipelineView />}
        {activeView === "documents" && <DocumentsView />}
        {activeView === "outreach" && <OutreachView />}
        {activeView === "insights" && <InsightsView />}
        {activeView === "settings" && (
          <SettingsView
            trustedMode={trustedMode}
            setTrustedMode={setTrustedMode}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 py-6 text-center text-xs text-slate-500 bg-[#0f172a]/50">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>CareerHarness Platform — DeepSeek Loop & BYOK Architecture</span>
          <span className="font-mono text-slate-400">Zero Stubs • Zero Social Login • Fail-Closed</span>
        </div>
      </footer>
    </div>
  );
}

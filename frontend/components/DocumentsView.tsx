"use client";

import React, { useState } from "react";
import {
  BookOpen,
  CheckCircle2,
  Download,
  Eye,
  FileCheck,
  GitBranch,
  Layers,
  Sparkles,
  UserCheck,
} from "lucide-react";

interface StoryItem {
  id: string;
  title: string;
  situation: string;
  task: string;
  action: string;
  result: string;
  metrics: string[];
  skills: string[];
  verified: boolean;
}

const SAMPLE_STORIES: StoryItem[] = [
  {
    id: "story-1",
    title: "High-Throughput Ingestion Overhaul",
    situation: "Legacy ingestion pipeline experienced OOM crashes during 10x traffic surges.",
    task: "Rebuild data worker pool with asynchronous stream processing and strict backpressure.",
    action: "Migrated architecture to Python asyncio with Redis queues and PostgreSQL batch partitioning.",
    result: "Sustained 10M events per day with latency reduced by 45% and $250k saved annually.",
    metrics: ["10x", "10M", "45%", "$250k"],
    skills: ["Python", "FastAPI", "Redis", "PostgreSQL"],
    verified: true,
  },
  {
    id: "story-2",
    title: "Distributed Fault-Tolerant Cache Redesign",
    situation: "Cross-region database read bottlenecks increased p99 API latency to 450ms.",
    task: "Implement distributed multi-tier caching layer with optimistic concurrency control.",
    action: "Architected cache-aside pattern using Redis Clusters with background cache invalidation relays.",
    result: "Dropped p99 API latency from 450ms to 42ms (90% reduction) with 99.99% cache availability.",
    metrics: ["450ms", "42ms", "90%", "99.99%"],
    skills: ["Redis", "Distributed Systems", "PostgreSQL"],
    verified: true,
  },
  {
    id: "story-3",
    title: "Global Multi-Tenant Billing Gateway",
    situation: "Payment failure rates increased during high-volume enterprise month-end billing runs.",
    task: "Engineer an idempotent, transactional billing worker queue with automatic retry exponential backoff.",
    action: "Built transactional outbox relay with AES-256 encrypted payload handling and webhook verification.",
    result: "Eliminated double-charge errors completely; processed $12M in gross transactions with 100% auditability.",
    metrics: ["$12M", "100%"],
    skills: ["Python", "PostgreSQL", "TDD", "Security"],
    verified: true,
  },
];

export function DocumentsView() {
  const [activeTab, setActiveTab] = useState<"versions" | "stories">("versions");
  const [stories, setStories] = useState<StoryItem[]>(SAMPLE_STORIES);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">Documents, Versions & Story Bank</h2>
          <p className="text-slate-400 text-xs mt-0.5">
            Immutable document lineage (VR-01..03), verified STAR story bank, and ATS single-column PDF generation.
          </p>
        </div>

        {/* Tab Toggle */}
        <div className="flex bg-slate-900 border border-slate-800 rounded-lg p-1">
          <button
            onClick={() => setActiveTab("versions")}
            className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-md text-xs font-medium transition-colors ${
              activeTab === "versions"
                ? "bg-slate-800 text-sky-400 shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <GitBranch className="h-3.5 w-3.5" />
            <span>Document Versions (4)</span>
          </button>
          <button
            onClick={() => setActiveTab("stories")}
            className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-md text-xs font-medium transition-colors ${
              activeTab === "stories"
                ? "bg-slate-800 text-sky-400 shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <BookOpen className="h-3.5 w-3.5" />
            <span>STAR Story Bank (3)</span>
          </button>
        </div>
      </div>

      {activeTab === "versions" ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Master Resume Card */}
          <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                MASTER RESUME (v1.0)
              </span>
              <span className="text-xs text-slate-500 font-mono">Immutable</span>
            </div>
            <div>
              <h3 className="font-bold text-white text-base">Senior Software Engineer — Master</h3>
              <p className="text-xs text-slate-400 mt-1">
                Verified root document containing 4 core roles, 18 verified skills, and 14 measurable impact bullets.
              </p>
            </div>

            <div className="pt-2 border-t border-slate-800 space-y-2 text-xs">
              <div className="flex justify-between text-slate-400">
                <span>Verified Skills:</span>
                <span className="text-slate-200 font-medium">18 skills</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Conversion Rate:</span>
                <span className="text-emerald-400 font-medium">37.5% Interview Rate</span>
              </div>
            </div>

            <div className="pt-2 flex gap-2">
              <button
                onClick={() => window.open("/api/vault/master/pdf", "_blank")}
                className="flex-1 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors"
              >
                <Download className="h-3.5 w-3.5" />
                <span>Download ATS PDF</span>
              </button>
            </div>
          </div>

          {/* Tailored Branches (Lineage) */}
          <div className="lg:col-span-2 p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="font-semibold text-white text-sm">Tailored Children & Application Branches</h3>
              <span className="text-xs text-slate-400">Zero Hallucination Guarantee (AT-02)</span>
            </div>

            <div className="space-y-3">
              <div className="p-4 rounded-lg bg-slate-800/60 border border-slate-700/80 flex items-start justify-between">
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-mono text-sky-400">v1.1 (Branch: Stripe)</span>
                    <span className="text-[11px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      Honesty Verified
                    </span>
                  </div>
                  <h4 className="font-semibold text-slate-200 text-sm">Staff Distributed Systems Engineer</h4>
                  <p className="text-xs text-slate-400">
                    Prioritized Redis clustering and async ingestion bullets. Overlap: 94%. Zero invented claims.
                  </p>
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => window.open("/api/vault/branches/stripe/pdf", "_blank")}
                    className="p-2 rounded bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs transition-colors"
                    title="Download ATS PDF"
                  >
                    <Download className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>

              <div className="p-4 rounded-lg bg-slate-800/60 border border-slate-700/80 flex items-start justify-between">
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-mono text-sky-400">v1.2 (Branch: Uber)</span>
                    <span className="text-[11px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      Honesty Verified
                    </span>
                  </div>
                  <h4 className="font-semibold text-slate-200 text-sm">Senior Backend Platform Engineer</h4>
                  <p className="text-xs text-slate-400">
                    Prioritized API latency reduction and microservices scale. Overlap: 91%.
                  </p>
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => window.open("/api/vault/branches/uber/pdf", "_blank")}
                    className="p-2 rounded bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs transition-colors"
                    title="Download ATS PDF"
                  >
                    <Download className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* STAR Story Bank View */
        <div className="space-y-4">
          {stories.map((story) => (
            <div
              key={story.id}
              className="p-5 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 transition-colors space-y-3"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center space-x-2">
                    <h3 className="font-bold text-white text-base">{story.title}</h3>
                    <span className="text-[11px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
                      <CheckCircle2 className="h-3 w-3" />
                      <span>Verified Against Master</span>
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {story.skills.map((s) => (
                      <span key={s} className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-[11px] border border-slate-700">
                        {s}
                      </span>
                    ))}
                    {story.metrics.map((m) => (
                      <span key={m} className="px-2 py-0.5 rounded bg-sky-500/10 text-sky-300 text-[11px] font-mono border border-sky-500/20 font-semibold">
                        {m}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* STAR Breakdown */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3 pt-3 border-t border-slate-800 text-xs">
                <div className="p-2.5 rounded-lg bg-slate-800/40 border border-slate-800">
                  <span className="font-bold text-slate-400 uppercase text-[10px] tracking-wider block mb-1">Situation</span>
                  <p className="text-slate-300">{story.situation}</p>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-800/40 border border-slate-800">
                  <span className="font-bold text-slate-400 uppercase text-[10px] tracking-wider block mb-1">Task</span>
                  <p className="text-slate-300">{story.task}</p>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-800/40 border border-slate-800">
                  <span className="font-bold text-slate-400 uppercase text-[10px] tracking-wider block mb-1">Action</span>
                  <p className="text-slate-300">{story.action}</p>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-800/40 border border-slate-800">
                  <span className="font-bold text-slate-400 uppercase text-[10px] tracking-wider block mb-1">Result</span>
                  <p className="text-emerald-300 font-medium">{story.result}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

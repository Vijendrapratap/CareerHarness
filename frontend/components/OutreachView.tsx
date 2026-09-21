"use client";

import React, { useState } from "react";
import {
  Calendar,
  CheckCircle2,
  Clock,
  Code2,
  Mail,
  MessageSquare,
  Send,
  Sparkles,
  User,
  XCircle,
} from "lucide-react";

interface DraftMessage {
  id: string;
  recipientName: string;
  recipientRole: string;
  company: string;
  jobTitle: string;
  subject: string;
  body: string;
  status: "draft" | "pending_approval" | "sent";
}

interface InboundEmailItem {
  id: string;
  sender: string;
  subject: string;
  classification: "interview" | "assessment" | "rejection" | "request_info";
  timeAgo: string;
  summary: string;
}

const SAMPLE_DRAFTS: DraftMessage[] = [
  {
    id: "out-1",
    recipientName: "Alex Rivera",
    recipientRole: "Head of Infrastructure Engineering",
    company: "Stripe",
    jobTitle: "Staff Distributed Systems Engineer",
    subject: "Excited about Staff Distributed Systems Engineer role at Stripe - Candidate",
    body: `Hi Alex,\n\nI recently applied for the Staff Distributed Systems Engineer position at Stripe and wanted to reach out directly. I admire Stripe's reliability standards and high-availability architecture.\n\nA couple of quick highlights from my background:\n• Rebuilt distributed data worker pool supporting 10M events/day with 45% lower latency\n• Architected cross-region Redis cluster dropping p99 API latency by 90% with 99.99% availability\n\nI'd welcome the opportunity to chat if you have a few minutes this week.\n\nBest regards,\nCandidate`,
    status: "draft",
  },
  {
    id: "out-2",
    recipientName: "Sarah Chen",
    recipientRole: "Engineering Director",
    company: "Uber",
    jobTitle: "Senior Backend Platform Engineer",
    subject: "Excited about Senior Backend Platform Engineer role at Uber - Candidate",
    body: `Hi Sarah,\n\nI applied for the Senior Backend Platform Engineer role. Having scaled Python and microservice clusters to 100k active users, I would love to contribute to Uber's real-time matching pipelines.\n\nBest regards,\nCandidate`,
    status: "draft",
  },
];

const SAMPLE_INBOUND: InboundEmailItem[] = [
  {
    id: "in-1",
    sender: "recruiting@stripe.com",
    subject: "Invitation to Interview: Technical Screen at Stripe",
    classification: "interview",
    timeAgo: "2 hours ago",
    summary: "Recruiter shared Calendly link to schedule a 45-minute architectural discussion with the team.",
  },
  {
    id: "in-2",
    sender: "talent@uber.com",
    subject: "Next Steps: Online Technical Assessment (Hackerrank)",
    classification: "assessment",
    timeAgo: "Yesterday",
    summary: "75-minute algorithmic and concurrency coding assessment sent via Hackerrank link.",
  },
  {
    id: "in-3",
    sender: "careers@meta.com",
    subject: "Update on your application for Production Engineer",
    classification: "rejection",
    timeAgo: "3 days ago",
    summary: "Automated rejection letter. Status updated to rejected.",
  },
];

export function OutreachView() {
  const [drafts, setDrafts] = useState<DraftMessage[]>(SAMPLE_DRAFTS);
  const [sentCount, setSentCount] = useState(4);
  const dailyLimit = 15;

  const handleSend = (id: string) => {
    setDrafts((prev) =>
      prev.map((d) => (d.id === id ? { ...d, status: "sent" } : d))
    );
    setSentCount((c) => c + 1);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">Hiring Manager Outreach & Reply Intelligence</h2>
          <p className="text-slate-400 text-xs mt-0.5">
            Personalized story-bank cold emailing with strict 15/day rate limit (GT-04) and NLP recruiter reply classifier (GT-05).
          </p>
        </div>

        {/* Quota Progress */}
        <div className="p-3 bg-slate-900 border border-slate-800 rounded-lg flex items-center gap-3">
          <div className="text-right">
            <span className="text-xs text-slate-400">Daily Send Cap (GT-04):</span>
            <div className="text-sm font-bold text-white font-mono">{sentCount} / {dailyLimit} Sent</div>
          </div>
          <div className="w-24 h-2 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-sky-500 rounded-full transition-all"
              style={{ width: `${(sentCount / dailyLimit) * 100}%` }}
            ></div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Outreach Drafter */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-white text-sm">Hiring Manager Outreach Drafts</h3>
            <span className="text-xs text-slate-400 font-mono">Story-Bank Grounded</span>
          </div>

          <div className="space-y-4">
            {drafts.map((draft) => (
              <div
                key={draft.id}
                className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-3"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <span className="text-xs font-semibold text-sky-400">{draft.company}</span>
                    <h4 className="font-bold text-white text-base leading-snug">{draft.recipientName}</h4>
                    <p className="text-xs text-slate-400">{draft.recipientRole}</p>
                  </div>
                  <span
                    className={`text-[11px] font-semibold px-2 py-0.5 rounded border ${
                      draft.status === "sent"
                        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                        : "bg-amber-500/10 text-amber-400 border-amber-500/30"
                    }`}
                  >
                    {draft.status === "sent" ? "SENT" : "READY FOR APPROVAL"}
                  </span>
                </div>

                <div className="p-3 rounded-lg bg-slate-800/60 border border-slate-700/80 text-xs text-slate-300 font-sans whitespace-pre-line leading-relaxed">
                  {draft.body}
                </div>

                {draft.status !== "sent" && (
                  <div className="flex justify-end gap-2 pt-1">
                    <button
                      onClick={() => handleSend(draft.id)}
                      disabled={sentCount >= dailyLimit}
                      className="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-sky-600 hover:bg-sky-500 text-white transition-colors"
                    >
                      <Send className="h-3.5 w-3.5" />
                      <span>Approve & Send via Mailbox</span>
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Right: Recruiter Reply Stream (Classifier) */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-white text-sm">Recruiter Inbound Replies (GT-05)</h3>
            <span className="text-xs text-slate-400">Automated State Transition</span>
          </div>

          <div className="space-y-3">
            {SAMPLE_INBOUND.map((item) => (
              <div
                key={item.id}
                className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2 hover:border-slate-700 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    {item.classification === "interview" && (
                      <span className="flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                        <Calendar className="h-3 w-3" />
                        <span>INTERVIEW</span>
                      </span>
                    )}
                    {item.classification === "assessment" && (
                      <span className="flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
                        <Code2 className="h-3 w-3" />
                        <span>ASSESSMENT</span>
                      </span>
                    )}
                    {item.classification === "rejection" && (
                      <span className="flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                        <XCircle className="h-3 w-3" />
                        <span>REJECTION</span>
                      </span>
                    )}
                    <span className="text-xs font-medium text-slate-300">{item.sender}</span>
                  </div>
                  <span className="text-[11px] text-slate-500">{item.timeAgo}</span>
                </div>

                <h4 className="font-semibold text-white text-sm">{item.subject}</h4>
                <p className="text-xs text-slate-400 leading-relaxed">{item.summary}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

"use client";

import React, { useEffect, useRef, useState } from "react";
import { Shell } from "@/components/Shell";
import { api } from "@/lib/api";
import { listenOnce } from "@/lib/speech";

interface HistoryItem {
  step: string;
  prompt: string;
  answer: string;
  input_mode?: string;
}

interface CounselState {
  step: string | null;
  prompt: string;
  choices: any[];
  history?: HistoryItem[];
  done: boolean;
}

interface StepMeta {
  title: string;
  badge: string;
  coachIntro: string;
  placeholder: string;
  helperNote: string;
  quickStarters?: string[];
}

const STEPS_ORDER = [
  "linkedin",
  "resume",
  "target_work",
  "priority_role",
  "management",
  "location",
  "authorization",
  "preferences",
];

const STEP_METADATA: Record<string, StepMeta> = {
  linkedin: {
    title: "Public Presence & Professional Bio",
    badge: "Step 1 of 8",
    coachIntro:
      "Welcome to CareerHarness! I'm your AI Executive Career Counsellor. Let's calibrate your background to target high-signal opportunities. Share your LinkedIn profile URL or paste your summary/experience.",
    placeholder: "e.g. https://linkedin.com/in/username or paste your experience summary...",
    helperNote:
      "Used to calibrate your seniority level, company prestige pedigree, and public positioning.",
    quickStarters: [
      "https://linkedin.com/in/",
      "Senior Distributed Systems Engineer with 7+ years scaling backend architectures...",
      "Staff Full-Stack Architect specialized in TypeScript, Next.js, and cloud platforms...",
    ],
  },
  resume: {
    title: "Verified Skills & Quantified Achievements",
    badge: "Step 2 of 8",
    coachIntro:
      "Now let's extract your technical depth and metrics. Please upload your latest Resume (PDF). DeepSeek will automatically parse your verified skills, latency reductions, and ARR impact.",
    placeholder: "Upload your PDF resume",
    helperNote:
      "Strict PDF upload. Our parser extracts verified technologies and metric proof points for recruiter outreach.",
  },
  target_work: {
    title: "Next Career Ambition & Engineering Focus",
    badge: "Step 3 of 8",
    coachIntro:
      "What kind of work do you want to tackle next? Tell me about the engineering problems you love solving, desired tech stacks (e.g., Go, Python, Distributed Systems, ML/LLMs), or company stages (seed startup vs high-scale enterprise).",
    placeholder:
      "Describe the problems, architectures, or stacks you want to lead in your next role...",
    helperNote:
      "Directly calibrates Scout's autonomous job discovery algorithm and domain relevance ranking.",
    quickStarters: [
      "Staff/Senior Backend in Distributed Systems (Go, Python, Kafka, Kubernetes)",
      "AI / ML Systems Engineer scaling LLM inference, RAG, and fine-tuning",
      "Frontend Architect leading Design Systems, React, Next.js, and Web Performance",
      "Product-focused Full Stack Engineer shipping 0→1 SaaS applications rapidly",
    ],
  },
  priority_role: {
    title: "Primary Target Role (#1 Priority)",
    badge: "Step 4 of 8",
    coachIntro:
      "Based on your background and target work, I've mapped your top role matches below. Which one is your #1 Priority Role? Scout gives this role a 1.5× search weighting and crafts hyper-tailored outreach emails.",
    placeholder: "Select a recommended role or type your exact target title...",
    helperNote:
      "Receives 1.5× Scout search priority and customized recruiter outreach angles.",
  },
  management: {
    title: "Leadership & Scope of Impact",
    badge: "Step 5 of 8",
    coachIntro:
      "Have you managed people, led engineering squads, or owned end-to-end program roadmaps? Confirming management unlocks our Lead / Manager / Director search tracks and opens a 4th role slot.",
    placeholder: "Select your leadership experience below...",
    helperNote:
      "Unlocks 4th target role slot and directs outreach toward Team Lead / Engineering Manager positions.",
  },
  location: {
    title: "Location & Work Model Preference",
    badge: "Step 6 of 8",
    coachIntro:
      "Where do you want to work, and what is your preferred work setup? We will screen and filter opportunities according to your exact location and timezone requirements.",
    placeholder: "e.g. Remote (US & Europe), or Hybrid in San Francisco / New York...",
    helperNote:
      "Prevents misaligned recruiter outreach by enforcing strict location & work setup filters.",
    quickStarters: [
      "Remote (Global / Anywhere)",
      "Remote (US / North America)",
      "Hybrid or On-site (San Francisco / Bay Area)",
      "Hybrid or On-site (New York City)",
      "Hybrid / Remote (London / UK / Europe)",
      "Hybrid / Remote (Bengaluru / India)",
    ],
  },
  authorization: {
    title: "Work Authorization & Visa Status",
    badge: "Step 7 of 8",
    coachIntro:
      "What is your work authorization status in your target market? Do you require visa sponsorship, or are you authorized as a citizen or permanent resident?",
    placeholder: "e.g. Citizen / Permanent Resident, or Needs H-1B transfer, or Open to B2B...",
    helperNote:
      "Guarantees 0% wasted effort on employers that do not match your immigration needs.",
    quickStarters: [
      "Authorized to work (Citizen / Permanent Resident, No sponsorship needed)",
      "Requires Visa Sponsorship (H-1B, Skilled Worker, or Visa Transfer)",
      "Authorized via OPT / STEM OPT (requires future sponsorship)",
      "Open to B2B / C2C / Global Independent Contractor engagements",
    ],
  },
  preferences: {
    title: "Role Preferences & Dealbreakers",
    badge: "Step 8 of 8",
    coachIntro:
      "Final question to fine-tune your autonomous career engine: What do you want MORE of, and what are your absolute DEALBREAKERS to avoid?",
    placeholder:
      "e.g. More product autonomy and modern tech; avoid legacy codebases and uncompensated 24/7 on-call...",
    helperNote:
      "Scout uses these dealbreakers to automatically reject poor-fit job postings.",
    quickStarters: [
      "More autonomous ownership and modern tech; avoid legacy monoliths and 24/7 on-call",
      "More AI/LLM production systems; avoid micromanagement and excessive meetings",
      "More high-signal mentorship and competitive compensation; avoid early unverified pre-seed chaos",
      "Strong work-life balance and remote flexibility; avoid toxic crunch culture",
    ],
  },
};

export default function CounselPage() {
  const [counselState, setCounselState] = useState<CounselState | null>(null);
  const [answerText, setAnswerText] = useState("");
  const [inputMode, setInputMode] = useState<"text" | "mic">("text");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [listening, setListening] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadingResume, setUploadingResume] = useState(false);
  const [uploadedResume, setUploadedResume] = useState<{
    filename: string;
    skillsCount: number;
    resumeId: string;
  } | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadState();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [counselState?.step, counselState?.history?.length, isTyping]);

  async function loadState() {
    setLoading(true);
    setError(null);
    try {
      const data = await api<CounselState>("/api/counsel");
      setCounselState(data);
      if (data.done) {
        window.location.assign("/todos");
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to load counsellor state");
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleSpeak() {
    setError(null);
    setListening(true);
    try {
      const transcript = await listenOnce();
      setAnswerText(transcript);
      setInputMode("mic");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Microphone recognition failed");
      }
    } finally {
      setListening(false);
    }
  }

  async function processResumeFile(file: File) {
    if (!file) return;
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      setError("Please select a valid PDF file.");
      return;
    }
    setError(null);
    setUploadingResume(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch("/api/resumes/upload", {
        method: "POST",
        body: formData,
        credentials: "include",
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        let message = "Failed to upload resume PDF";
        if (typeof errJson.detail === "string") {
          message = errJson.detail;
        } else if (Array.isArray(errJson.detail)) {
          message = errJson.detail.map((d: any) => d.msg || JSON.stringify(d)).join(", ");
        }
        throw new Error(message);
      }
      const data = await res.json();
      const skillsCount = Array.isArray(data.extracted_skills) ? data.extracted_skills.length : 0;
      const refId = data.id || file.name;
      setUploadedResume({ filename: file.name, skillsCount, resumeId: refId });
      setAnswerText(refId);
      setInputMode("text");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to upload resume file");
      }
    } finally {
      setUploadingResume(false);
    }
  }

  function handleResumeUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) {
      processResumeFile(file);
    }
  }

  async function handleConfirmResume() {
    const refId = uploadedResume?.resumeId || answerText;
    if (!counselState?.step || !refId.trim()) return;

    setError(null);
    setSubmitting(true);
    setIsTyping(true);
    try {
      const res = await api<CounselState>("/api/counsel/answer", {
        method: "POST",
        body: JSON.stringify({
          step: counselState.step,
          text: refId.trim(),
          input_mode: "text",
        }),
      });
      setCounselState(res);
      setAnswerText("");
      setUploadedResume(null);
      if (res.done) {
        window.location.assign("/todos");
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to save resume");
      }
    } finally {
      setSubmitting(false);
      setTimeout(() => setIsTyping(false), 300);
    }
  }

  async function handleSaveAnswer(e?: React.FormEvent, overrideText?: string) {
    if (e) e.preventDefault();
    const textToSubmit = (overrideText !== undefined ? overrideText : answerText).trim();
    if (!counselState?.step || !textToSubmit) return;

    setError(null);
    setSubmitting(true);
    setIsTyping(true);
    try {
      const res = await api<CounselState>("/api/counsel/answer", {
        method: "POST",
        body: JSON.stringify({
          step: counselState.step,
          text: textToSubmit,
          input_mode: inputMode,
        }),
      });
      setCounselState(res);
      setAnswerText("");
      setInputMode("text");
      if (res.done) {
        window.location.assign("/todos");
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to save answer");
      }
    } finally {
      setSubmitting(false);
      setTimeout(() => setIsTyping(false), 300);
    }
  }

  const currentStep = counselState?.step || "";
  const activeMeta = STEP_METADATA[currentStep] || {
    title: counselState?.prompt || "Career Discovery",
    badge: "Discovery",
    coachIntro: counselState?.prompt || "",
    placeholder: "Type your response...",
    helperNote: "",
  };

  const completedStepsCount = counselState?.history?.length || 0;
  const currentStepIndex = currentStep ? STEPS_ORDER.indexOf(currentStep) : 0;
  const progressPercent = counselState?.done
    ? 100
    : Math.min(100, Math.round((completedStepsCount / 8) * 100));

  // Extract snapshot fields from history
  const historyMap = (counselState?.history || []).reduce<Record<string, string>>((acc, item) => {
    acc[item.step] = item.answer;
    return acc;
  }, {});

  return (
    <Shell title="Executive Career Counsellor">
      <div className="space-y-6">
        {/* Top Progress Banner */}
        <div className="neo-raised p-5 rounded-2xl flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3 w-full md:w-auto">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-teal-600 to-cyan-600 text-white flex items-center justify-center font-bold text-sm shadow-md">
              🎯
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-wider text-teal-800">
                  Onboarding Chat Stream
                </span>
                <span className="badge-teal text-[10px] py-0.5 px-2">
                  HubSpot Conversational Flow
                </span>
              </div>
              <p className="text-xs text-muted">
                {counselState?.done
                  ? "All 8 profile calibration steps completed."
                  : `Question ${currentStepIndex + 1} of 8: ${activeMeta.title}`}
              </p>
            </div>
          </div>

          {/* Stepper Progress Bar */}
          <div className="flex items-center gap-3 w-full md:w-72">
            <div className="w-full h-2.5 rounded-full bg-slate-200/80 overflow-hidden p-0.5 border border-slate-300/40">
              <div
                className="h-full rounded-full bg-gradient-to-r from-teal-500 via-cyan-500 to-emerald-500 transition-all duration-500 shadow-sm"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
            <span className="text-xs font-bold text-teal-800 shrink-0">
              {progressPercent}%
            </span>
          </div>
        </div>

        {/* Main 2-Column Hub: Left Chat Stream (HubSpot Style), Right Live Profile Snapshot */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Chat UI Stream */}
          <div className="lg:col-span-8 space-y-6">
            <div className="neo-card p-6 min-h-[550px] flex flex-col justify-between space-y-6">
              {loading ? (
                <div className="p-12 text-center text-muted space-y-3 my-auto">
                  <div className="inline-block h-8 w-8 rounded-full border-2 border-teal-600 border-t-transparent animate-spin" />
                  <p className="text-sm font-medium">Connecting to AI Career Counsellor...</p>
                </div>
              ) : counselState?.done ? (
                <div className="p-10 text-center space-y-5 my-auto animate-chat-in">
                  <div className="inline-flex h-16 w-16 rounded-3xl bg-emerald-100 text-emerald-700 items-center justify-center text-3xl font-bold mb-2 shadow-inner">
                    ✓
                  </div>
                  <h2 className="text-2xl font-bold text-ink">Career Profile Fully Calibrated!</h2>
                  <p className="text-xs text-muted max-w-md mx-auto leading-relaxed">
                    All 8 domain dimensions have been recorded and vaulted. Scout is now armed with your high-weighted target role, verified skills, and dealbreakers.
                  </p>
                  <button
                    onClick={() => window.location.assign("/todos")}
                    className="btn-teal px-8 py-3 text-xs font-bold uppercase tracking-wider shadow-lg"
                  >
                    View Targeted Jobs & Action Items →
                  </button>
                </div>
              ) : (
                <div className="space-y-6">
                  {/* Chat Timeline: History Bubbles */}
                  {counselState?.history && counselState.history.length > 0 && (
                    <div className="space-y-5">
                      {counselState.history.map((hist) => {
                        const meta = STEP_METADATA[hist.step];
                        return (
                          <div key={hist.step} className="space-y-3 animate-chat-in">
                            {/* AI Message */}
                            <div className="flex items-start gap-3 max-w-xl">
                              <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-teal-600 to-cyan-700 text-white flex items-center justify-center font-bold text-xs shadow-sm shrink-0 mt-0.5">
                                AI
                              </div>
                              <div className="neo-raised p-4 rounded-2xl rounded-tl-sm text-xs space-y-1 bg-white/70">
                                <div className="flex items-center gap-2">
                                  <span className="text-[11px] font-bold text-teal-800 uppercase tracking-wide">
                                    {meta?.title || hist.step.replace("_", " ")}
                                  </span>
                                  <span className="text-[10px] text-emerald-700 font-semibold">
                                    ✓ Saved
                                  </span>
                                </div>
                                <p className="text-ink/80 leading-relaxed">
                                  {meta?.coachIntro || hist.prompt}
                                </p>
                              </div>
                            </div>

                            {/* Candidate User Answer Bubble */}
                            <div className="flex items-start justify-end gap-3 max-w-xl ml-auto">
                              <div className="p-4 rounded-2xl rounded-tr-sm bg-gradient-to-br from-teal-700 via-teal-800 to-cyan-900 text-white text-xs shadow-md space-y-1 max-w-md">
                                <div className="flex items-center justify-between gap-4 text-[10px] text-teal-200">
                                  <span className="font-semibold uppercase tracking-wider">Candidate</span>
                                  {hist.input_mode === "mic" && <span>🎙️ Spoken</span>}
                                </div>
                                <p className="font-medium leading-relaxed break-words whitespace-pre-wrap">
                                  {hist.answer}
                                </p>
                              </div>
                              <div className="h-9 w-9 rounded-xl bg-slate-800 text-white flex items-center justify-center font-bold text-xs shadow-sm shrink-0 mt-0.5">
                                You
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* Active Question Bubble (HubSpot One-Question-at-a-Time Focus) */}
                  <div className="space-y-4 animate-chat-in pt-2">
                    <div className="flex items-start gap-3 max-w-xl">
                      <div className="h-10 w-10 rounded-2xl bg-gradient-to-br from-teal-600 via-teal-700 to-cyan-700 text-white flex items-center justify-center font-bold text-sm shadow-md shadow-teal-700/20 shrink-0 mt-0.5">
                        AI
                      </div>
                      <div className="neo-card p-5 rounded-2xl rounded-tl-sm space-y-2 border border-teal-500/30 bg-white/80 shadow-md">
                        <div className="flex items-center justify-between gap-2">
                          <span className="badge-teal text-[10px] py-0.5 px-2 font-bold uppercase tracking-wider">
                            {activeMeta.badge}
                          </span>
                          <span className="text-[11px] text-muted font-medium">
                            DeepSeek Career Advisor
                          </span>
                        </div>
                        <h3 className="text-base font-bold text-ink leading-snug">
                          {activeMeta.title}
                        </h3>
                        <p className="text-xs text-ink/90 leading-relaxed font-normal">
                          {activeMeta.coachIntro}
                        </p>
                        {activeMeta.helperNote && (
                          <div className="text-[11px] text-teal-900 bg-teal-50/90 p-2.5 rounded-xl border border-teal-200/70 font-medium flex items-center gap-2 mt-2">
                            <span className="text-sm">💡</span>
                            <span>{activeMeta.helperNote}</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Typing Animation Indicator */}
                    {isTyping && (
                      <div className="flex items-center gap-2 text-xs text-teal-700 pl-14">
                        <div className="flex gap-1 items-center">
                          <span className="h-1.5 w-1.5 rounded-full bg-teal-600 typing-dot" />
                          <span className="h-1.5 w-1.5 rounded-full bg-teal-600 typing-dot" />
                          <span className="h-1.5 w-1.5 rounded-full bg-teal-600 typing-dot" />
                        </div>
                        <span className="text-[11px] font-medium animate-pulse">
                          AI Counsellor is tailoring next step...
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Interactive Input Form for Active Step */}
              {!loading && !counselState?.done && (
                <div className="pt-4 border-t border-slate-200/80 space-y-4">
                  {/* Step 2: STRICT RESUME PDF UPLOAD (NO TEXTAREA, NO MIC) */}
                  {currentStep === "resume" ? (
                    <div className="space-y-4">
                      <div
                        onDragOver={(e) => {
                          e.preventDefault();
                          if (!uploadingResume) setIsDragging(true);
                        }}
                        onDragLeave={() => setIsDragging(false)}
                        onDrop={(e) => {
                          e.preventDefault();
                          setIsDragging(false);
                          if (!uploadingResume && e.dataTransfer.files?.[0]) {
                            processResumeFile(e.dataTransfer.files[0]);
                          }
                        }}
                        className={`p-8 rounded-2xl border-2 border-dashed transition-all duration-200 text-center space-y-4 ${
                          isDragging
                            ? "border-teal-500 bg-teal-50/80 scale-[1.01]"
                            : uploadedResume
                            ? "border-emerald-400 bg-emerald-50/20"
                            : "border-slate-300 hover:border-teal-400 bg-slate-50/40"
                        }`}
                      >
                        <div className="inline-flex h-16 w-16 rounded-2xl bg-teal-100/80 text-teal-700 items-center justify-center text-3xl shadow-inner mx-auto">
                          📄
                        </div>

                        <div className="space-y-1">
                          <h4 className="text-sm font-bold text-ink">
                            {uploadedResume
                              ? "Resume Document Uploaded & Parsed"
                              : "Upload your Resume (PDF format)"}
                          </h4>
                          <p className="text-xs text-muted max-w-md mx-auto">
                            Drag and drop your PDF resume here, or click browse below. DeepSeek will
                            extract verified skills, metrics, and role history.
                          </p>
                        </div>

                        <input
                          type="file"
                          id="resume-file-input"
                          accept=".pdf,application/pdf"
                          onChange={handleResumeUpload}
                          disabled={uploadingResume}
                          className="hidden"
                        />

                        {!uploadedResume && !uploadingResume && (
                          <div>
                            <label
                              htmlFor="resume-file-input"
                              className="btn-teal inline-flex items-center justify-center gap-2 px-6 py-2.5 text-xs font-bold uppercase tracking-wider cursor-pointer shadow-md hover:shadow-lg transition-all"
                            >
                              <span>Choose Resume PDF</span>
                            </label>
                            <p className="text-[11px] text-muted mt-2">
                              PDF only • Max file size 10MB
                            </p>
                          </div>
                        )}

                        {uploadingResume && (
                          <div className="p-4 rounded-xl bg-teal-50/80 border border-teal-200 flex flex-col items-center justify-center gap-2 text-teal-800">
                            <div className="h-6 w-6 rounded-full border-2 border-teal-600 border-t-transparent animate-spin" />
                            <p className="text-xs font-semibold">
                              Parsing PDF document and extracting skills with AI...
                            </p>
                            <span className="text-[11px] text-teal-600">
                              This takes just a few seconds
                            </span>
                          </div>
                        )}

                        {uploadedResume && !uploadingResume && (
                          <div className="max-w-md mx-auto p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-left flex items-start justify-between gap-3 shadow-sm">
                            <div className="space-y-1">
                              <div className="flex items-center gap-2">
                                <span className="text-emerald-700 font-bold text-sm">✓</span>
                                <span className="text-xs font-bold text-emerald-950 truncate max-w-[220px]">
                                  {uploadedResume.filename}
                                </span>
                              </div>
                              <p className="text-[11px] text-emerald-800 font-medium">
                                Successfully parsed • {uploadedResume.skillsCount} skills detected & vaulted.
                              </p>
                            </div>
                            <label
                              htmlFor="resume-file-input"
                              className="text-[11px] font-semibold text-teal-700 hover:text-teal-900 underline cursor-pointer shrink-0 py-1"
                            >
                              Change PDF
                            </label>
                          </div>
                        )}
                      </div>

                      {error && (
                        <div className="p-3 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-xl">
                          {error}
                        </div>
                      )}

                      <div className="flex items-center justify-end gap-3">
                        <button
                          type="button"
                          onClick={handleConfirmResume}
                          disabled={submitting || uploadingResume || !uploadedResume}
                          className="btn-teal px-8 py-3 text-xs font-bold uppercase tracking-wider disabled:opacity-50 shadow-md flex items-center gap-2"
                        >
                          <span>
                            {submitting
                              ? "Saving Resume..."
                              : "Confirm Resume & Continue to Target Work →"}
                          </span>
                        </button>
                      </div>
                    </div>
                  ) : currentStep === "priority_role" ? (
                    /* Step 4: PRIORITY ROLE (INTERACTIVE ROLE CARDS + SAFE CAPPING) */
                    <div className="space-y-4">
                      {counselState?.choices && counselState.choices.length > 0 && (
                        <div className="space-y-2">
                          <p className="text-xs font-bold uppercase text-muted">
                            Recommended Role Matches (Click to Select):
                          </p>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                            {counselState.choices.map((choice: string, idx: number) => {
                              const title = choice
                                .replace(/[-_]/g, " ")
                                .replace(/\b\w/g, (c) => c.toUpperCase());
                              const isSelected = answerText === choice;
                              return (
                                <button
                                  key={choice}
                                  type="button"
                                  onClick={() => handleSaveAnswer(undefined, choice)}
                                  className={`p-3.5 rounded-xl text-left transition-all border ${
                                    isSelected
                                      ? "neo-pressed text-teal-800 border-teal-500 font-bold"
                                      : "neo-raised text-ink hover:border-teal-400 hover:text-teal-800"
                                  }`}
                                >
                                  <div className="flex items-center justify-between text-[11px] text-muted mb-1">
                                    <span className="font-semibold text-teal-700">
                                      {idx === 0
                                        ? "⭐ #1 Recommended"
                                        : idx === 1
                                        ? "🎯 Target Focus"
                                        : "💼 Match Option"}
                                    </span>
                                    <span className="text-[10px]">Instant Select →</span>
                                  </div>
                                  <p className="text-xs font-bold text-ink">{title}</p>
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {/* Custom Title Option */}
                      <form onSubmit={(e) => handleSaveAnswer(e)} className="space-y-3 pt-2">
                        <label className="block text-xs font-semibold uppercase tracking-wider text-muted">
                          Or Enter a Custom Target Role Title:
                        </label>
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={answerText}
                            onChange={(e) => setAnswerText(e.target.value)}
                            placeholder="e.g. Principal Staff Engineer or Lead Architect..."
                            className="neo-inset flex-1 px-4 py-2.5 text-xs text-ink bg-transparent focus:outline-none focus:ring-2 focus:ring-teal-500/30 rounded-xl"
                          />
                          <button
                            type="submit"
                            disabled={submitting || !answerText.trim()}
                            className="btn-teal px-6 py-2.5 text-xs font-bold uppercase tracking-wider disabled:opacity-50"
                          >
                            Set Priority →
                          </button>
                        </div>
                      </form>

                      {error && (
                        <div className="p-3 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-xl">
                          {error}
                        </div>
                      )}
                    </div>
                  ) : currentStep === "management" ? (
                    /* Step 5: MANAGEMENT EXPERIENCE (INTERACTIVE LEADERSHIP CARDS) */
                    <div className="space-y-4">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <button
                          type="button"
                          onClick={() => handleSaveAnswer(undefined, "yes")}
                          disabled={submitting}
                          className="neo-raised p-5 rounded-2xl text-left hover:border-emerald-400 hover:scale-[1.01] transition-all space-y-2 border border-emerald-500/20 bg-emerald-50/30"
                        >
                          <div className="flex items-center gap-2">
                            <span className="text-xl">👥</span>
                            <span className="text-xs font-bold uppercase text-emerald-800 tracking-wider">
                              Leadership Experience
                            </span>
                          </div>
                          <h4 className="text-sm font-bold text-ink">
                            Yes, I have managed people or programs
                          </h4>
                          <p className="text-[11px] text-muted leading-relaxed">
                            Unlocks our Engineering Manager / Lead search tracks and opens a 4th
                            target role slot.
                          </p>
                          <span className="inline-block text-xs font-bold text-emerald-700 pt-1">
                            Select Leadership Track →
                          </span>
                        </button>

                        <button
                          type="button"
                          onClick={() => handleSaveAnswer(undefined, "no")}
                          disabled={submitting}
                          className="neo-raised p-5 rounded-2xl text-left hover:border-teal-400 hover:scale-[1.01] transition-all space-y-2 border border-slate-300 bg-slate-50/40"
                        >
                          <div className="flex items-center gap-2">
                            <span className="text-xl">⚡</span>
                            <span className="text-xs font-bold uppercase text-teal-800 tracking-wider">
                              Individual Contributor
                            </span>
                          </div>
                          <h4 className="text-sm font-bold text-ink">
                            No, focus on Individual Contributor (IC)
                          </h4>
                          <p className="text-[11px] text-muted leading-relaxed">
                            Focuses 100% on hands-on architecture, technical depth, and senior
                            specialist engineering roles.
                          </p>
                          <span className="inline-block text-xs font-bold text-teal-700 pt-1">
                            Select IC Track →
                          </span>
                        </button>
                      </div>

                      {error && (
                        <div className="p-3 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-xl">
                          {error}
                        </div>
                      )}
                    </div>
                  ) : (
                    /* ALL OTHER STEPS: TEXT + VOICE + QUICK STARTERS */
                    <div className="space-y-4">
                      {/* Quick Starters Inspiration Chips */}
                      {activeMeta.quickStarters && activeMeta.quickStarters.length > 0 && (
                        <div className="space-y-1.5">
                          <p className="text-[11px] font-bold uppercase text-muted tracking-wider">
                            Suggested Starters (Click to fill):
                          </p>
                          <div className="flex flex-wrap gap-2">
                            {activeMeta.quickStarters.map((starter) => (
                              <button
                                key={starter}
                                type="button"
                                onClick={() => {
                                  setAnswerText(starter);
                                  setInputMode("text");
                                }}
                                className="px-3 py-1.5 text-xs font-medium rounded-xl neo-raised text-ink hover:text-teal-700 hover:border-teal-400 text-left transition-all"
                              >
                                {starter}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}

                      <form onSubmit={(e) => handleSaveAnswer(e)} className="space-y-4">
                        <div>
                          <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-2">
                            Your Response (Type or Dictate via Voice)
                          </label>
                          <textarea
                            rows={3}
                            required
                            value={answerText}
                            onChange={(e) => {
                              setAnswerText(e.target.value);
                              setInputMode("text");
                            }}
                            className="neo-inset w-full p-4 text-xs text-ink bg-transparent focus:outline-none focus:ring-2 focus:ring-teal-500/30 rounded-xl resize-none transition-all placeholder:text-muted/60 leading-relaxed"
                            placeholder={activeMeta.placeholder}
                          />
                        </div>

                        {error && (
                          <div className="p-3 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-xl">
                            {error}
                          </div>
                        )}

                        <div className="flex items-center justify-between gap-4 pt-1">
                          <button
                            type="button"
                            onClick={handleSpeak}
                            disabled={listening || submitting}
                            className={`px-4 py-2.5 text-xs font-semibold rounded-xl flex items-center gap-2 transition-all ${
                              listening
                                ? "bg-rose-100 text-rose-700 border border-rose-300 animate-pulse shadow-sm"
                                : "neo-raised text-ink hover:text-teal-700 hover:-translate-y-0.5"
                            }`}
                          >
                            <span>🎙️</span>
                            <span>{listening ? "Listening..." : "Speak Answer"}</span>
                          </button>

                          <button
                            type="submit"
                            disabled={submitting || !answerText.trim()}
                            className="btn-teal px-8 py-2.5 text-xs font-bold uppercase tracking-wider disabled:opacity-50 shadow-md flex items-center gap-2"
                          >
                            <span>{submitting ? "Saving..." : "Send Answer →"}</span>
                          </button>
                        </div>
                      </form>
                    </div>
                  )}
                </div>
              )}
              <div ref={chatEndRef} />
            </div>
          </div>

          {/* Right Column: HubSpot-style Live Candidate Profile Snapshot */}
          <div className="lg:col-span-4 space-y-6">
            <div className="neo-card p-6 space-y-5 sticky top-6">
              <div className="flex items-center justify-between border-b border-slate-200/80 pb-3">
                <div className="flex items-center gap-2">
                  <span className="text-base">👤</span>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-ink">
                    Candidate Profile Snapshot
                  </h3>
                </div>
                <span className="badge-teal text-[10px] py-0.5 px-2 font-bold">
                  {completedStepsCount}/8 Calibrated
                </span>
              </div>

              {/* Real-time Checklist of Information Collected */}
              <div className="space-y-3.5 text-xs">
                {/* 1. LinkedIn */}
                <div className="p-3 rounded-xl bg-slate-50/70 border border-slate-200/60 space-y-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="font-semibold text-slate-700">1. Public Presence</span>
                    {historyMap.linkedin ? (
                      <span className="text-emerald-700 font-bold">✓ Calibrated</span>
                    ) : (
                      <span className="text-muted">Pending</span>
                    )}
                  </div>
                  <p className="text-[11px] text-ink/80 truncate">
                    {historyMap.linkedin || "Not provided yet"}
                  </p>
                </div>

                {/* 2. Resume Vault */}
                <div className="p-3 rounded-xl bg-slate-50/70 border border-slate-200/60 space-y-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="font-semibold text-slate-700">2. Resume Document</span>
                    {historyMap.resume ? (
                      <span className="text-emerald-700 font-bold">✓ Vaulted</span>
                    ) : (
                      <span className="text-muted">Pending</span>
                    )}
                  </div>
                  <p className="text-[11px] text-ink/80 truncate">
                    {historyMap.resume ? "PDF Parsed & Skills Extracted" : "Not uploaded yet"}
                  </p>
                </div>

                {/* 3. Target Work */}
                <div className="p-3 rounded-xl bg-slate-50/70 border border-slate-200/60 space-y-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="font-semibold text-slate-700">3. Target Ambition</span>
                    {historyMap.target_work ? (
                      <span className="text-emerald-700 font-bold">✓ Calibrated</span>
                    ) : (
                      <span className="text-muted">Pending</span>
                    )}
                  </div>
                  <p className="text-[11px] text-ink/80 truncate">
                    {historyMap.target_work || "Not specified yet"}
                  </p>
                </div>

                {/* 4. Priority Role */}
                <div className="p-3 rounded-xl bg-slate-50/70 border border-slate-200/60 space-y-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="font-semibold text-slate-700">4. Priority Role</span>
                    {historyMap.priority_role ? (
                      <span className="text-emerald-700 font-bold">⭐ 1.5× Weight</span>
                    ) : (
                      <span className="text-muted">Pending</span>
                    )}
                  </div>
                  <p className="text-[11px] text-ink/80 font-medium truncate">
                    {historyMap.priority_role || "Not selected yet"}
                  </p>
                </div>

                {/* 5. Leadership */}
                <div className="p-3 rounded-xl bg-slate-50/70 border border-slate-200/60 space-y-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="font-semibold text-slate-700">5. Leadership Scope</span>
                    {historyMap.management ? (
                      <span className="text-emerald-700 font-bold">✓ Set</span>
                    ) : (
                      <span className="text-muted">Pending</span>
                    )}
                  </div>
                  <p className="text-[11px] text-ink/80 truncate">
                    {historyMap.management || "Not evaluated yet"}
                  </p>
                </div>

                {/* 6. Location */}
                <div className="p-3 rounded-xl bg-slate-50/70 border border-slate-200/60 space-y-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="font-semibold text-slate-700">6. Location Model</span>
                    {historyMap.location ? (
                      <span className="text-emerald-700 font-bold">✓ Filter Set</span>
                    ) : (
                      <span className="text-muted">Pending</span>
                    )}
                  </div>
                  <p className="text-[11px] text-ink/80 truncate">
                    {historyMap.location || "Not specified yet"}
                  </p>
                </div>

                {/* 7. Visa Authorization */}
                <div className="p-3 rounded-xl bg-slate-50/70 border border-slate-200/60 space-y-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="font-semibold text-slate-700">7. Authorization</span>
                    {historyMap.authorization ? (
                      <span className="text-emerald-700 font-bold">✓ Verified</span>
                    ) : (
                      <span className="text-muted">Pending</span>
                    )}
                  </div>
                  <p className="text-[11px] text-ink/80 truncate">
                    {historyMap.authorization || "Not specified yet"}
                  </p>
                </div>

                {/* 8. Preferences & Dealbreakers */}
                <div className="p-3 rounded-xl bg-slate-50/70 border border-slate-200/60 space-y-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="font-semibold text-slate-700">8. Dealbreakers</span>
                    {historyMap.preferences ? (
                      <span className="text-emerald-700 font-bold">✓ Active</span>
                    ) : (
                      <span className="text-muted">Pending</span>
                    )}
                  </div>
                  <p className="text-[11px] text-ink/80 truncate">
                    {historyMap.preferences || "Not configured yet"}
                  </p>
                </div>
              </div>

              {/* Info Callout */}
              <div className="p-3.5 rounded-xl bg-teal-50/60 border border-teal-200/60 text-[11px] text-teal-900 leading-relaxed">
                <span className="font-bold">Autonomous Match Engine:</span> Scout runs on a 2-hour
                polling cycle matching verified vacancies against this matrix.
              </div>
            </div>
          </div>
        </div>
      </div>
    </Shell>
  );
}

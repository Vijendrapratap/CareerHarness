"use client";

import React, { useEffect, useRef, useState } from "react";
import { Shell } from "@/components/Shell";
import { api, pageForStage } from "@/lib/api";
import { listenOnce } from "@/lib/speech";
import { FactQuestion } from "@/components/FactQuestion";

type OnboardingStage = "resume" | "linkedin" | "target_jobs" | "live_chat";

interface CatalogRole {
  id: string;
  title: string;
  family: string;
  aliases?: string[];
  baseline_skills?: string[];
  is_leadership?: boolean;
}

interface ChatMessage {
  id: string;
  role: "assistant" | "user";
  content: string;
  timestamp: string;
  inputMode?: "text" | "mic";
}

interface PersonaState {
  resumeFilename?: string;
  resumeSkillsCount?: number;
  extractedSkills: string[];
  linkedinUrl?: string;
  targetRoles: string[];
  priorityRole?: string;
  management?: boolean;
  location?: string;
  authorization?: string;
  preferences?: string;
}

export default function CounselPage() {
  const [currentStage, setCurrentStage] = useState<OnboardingStage>("resume");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Resume State
  const [uploadingResume, setUploadingResume] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadedResume, setUploadedResume] = useState<{
    filename: string;
    skillsCount: number;
    resumeId: string;
    extractedSkills: string[];
  } | null>(null);

  // LinkedIn State
  const [linkedinInput, setLinkedinInput] = useState("");
  const [linkedinHeadline, setLinkedinHeadline] = useState("");
  const [resumeDone, setResumeDone] = useState(false);
  const [savingLinkedin, setSavingLinkedin] = useState(false);

  // Target Roles State
  const [catalogRoles, setCatalogRoles] = useState<CatalogRole[]>([]);
  const [roleSearchQuery, setRoleSearchQuery] = useState("");
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);
  const [savingRoles, setSavingRoles] = useState(false);
  const [isRoleDropdownOpen, setIsRoleDropdownOpen] = useState(false);

  // Live Chat State (Optional / Advisory)
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInputText, setChatInputText] = useState("");
  const [inputMode, setInputMode] = useState<"text" | "mic">("text");
  const [sendingChat, setSendingChat] = useState(false);
  const [listening, setListening] = useState(false);
  const [isAiTyping, setIsAiTyping] = useState(false);
  const [finalizingPersona, setFinalizingPersona] = useState(false);
  const [confirmedSkills, setConfirmedSkills] = useState<string[]>([]);
  const [savingSkills, setSavingSkills] = useState(false);
  const [skillsSaved, setSkillsSaved] = useState(false);
  const [factsVersion, setFactsVersion] = useState(0);

  // Live Persona State
  const [persona, setPersona] = useState<PersonaState>({
    extractedSkills: [],
    targetRoles: [],
  });

  const chatEndRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // A superseded run (StrictMode double-invoke, fast navigation) must not apply stale state.
    let cancelled = false;
    initOnboarding(() => cancelled);
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages, isAiTyping]);

  async function initOnboarding(isCancelled: () => boolean) {
    setLoading(true);
    setError(null);
    try {
      const [catalog, counselState, selectedRolesData] = await Promise.all([
        api<CatalogRole[]>("/api/roles/catalog").catch(() => []),
        api<any>("/api/counsel").catch(() => null),
        api<any[]>("/api/roles").catch(() => []),
      ]);
      if (isCancelled()) return;
      setCatalogRoles(catalog);

      // Check existing history to determine where candidate is
      const history: Array<{ step: string; answer: string }> = counselState?.history || [];
      const histMap = history.reduce<Record<string, string>>((acc, h) => {
        acc[h.step] = h.answer;
        return acc;
      }, {});

      // Build initial persona from existing data
      const initialPersona: PersonaState = {
        extractedSkills: [],
        targetRoles: [],
        linkedinUrl:
          histMap.linkedin && histMap.linkedin !== "[Skipped]" ? histMap.linkedin : undefined,
        location: histMap.location,
        authorization: histMap.authorization,
        preferences: histMap.preferences,
      };

      setResumeDone(Boolean(histMap.resume));

      if (Array.isArray(selectedRolesData) && selectedRolesData.length > 0) {
        const roleIds = selectedRolesData.map((r) => r.role_id || r.id);
        setSelectedRoleIds(roleIds);
        initialPersona.targetRoles = roleIds;
        initialPersona.priorityRole = roleIds[0];
      }

      setPersona(initialPersona);

      // Determine starting screen based on completed information
      if (histMap.target_work || selectedRolesData.length > 0) {
        setCurrentStage("live_chat");
        startLiveChatSession(initialPersona, catalog);
      } else if (histMap.linkedin) {
        setCurrentStage("target_jobs");
      } else if (histMap.resume) {
        setCurrentStage("linkedin");
      } else {
        setCurrentStage("resume");
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to initialize onboarding");
      }
    } finally {
      if (!isCancelled()) setLoading(false);
    }
  }

  // --------------------------------------------------------------------------
  // STAGE 1: RESUME UPLOAD
  // --------------------------------------------------------------------------
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
      const extractedSkills: string[] = Array.isArray(data.extracted_skills)
        ? data.extracted_skills.map((s: { name: string } | string) => (typeof s === "string" ? s : s.name))
        : [];
      const refId = data.id || file.name;

      const resumeInfo = {
        filename: file.name,
        skillsCount: extractedSkills.length,
        resumeId: refId,
        extractedSkills,
      };

      setUploadedResume(resumeInfo);
      setConfirmedSkills([]);
      setSkillsSaved(false);
      setPersona((prev) => ({
        ...prev,
        resumeFilename: file.name,
        resumeSkillsCount: extractedSkills.length,
        extractedSkills,
      }));

      // Record resume answer in counsel flow
      await api("/api/counsel/answer", {
        method: "POST",
        body: JSON.stringify({
          step: "resume",
          text: refId,
          input_mode: "text",
        }),
      });
      setResumeDone(true);
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

  async function handleConfirmResumeSkills() {
    setSavingSkills(true);
    setError(null);
    try {
      await api("/api/fit/fixes/confirm-skills", {
        method: "POST",
        body: JSON.stringify({ skills: confirmedSkills }),
      });
      setSkillsSaved(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not save your skills");
    } finally {
      setSavingSkills(false);
    }
  }

  function handleResumeChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) processResumeFile(file);
  }

  function handleContinueFromResume() {
    if (!hasResume) {
      setError("Please upload your resume PDF before continuing.");
      return;
    }
    setError(null);
    setCurrentStage("linkedin");
  }

  // --------------------------------------------------------------------------
  // STAGE 2: LINKEDIN PROFILE (OPTIONAL / SKIPPABLE)
  // --------------------------------------------------------------------------
  async function handleSaveLinkedin(skip: boolean = false) {
    setError(null);
    setSavingLinkedin(true);
    const headline = skip ? "" : linkedinHeadline.trim();
    const url = skip ? "" : linkedinInput.trim();
    const valueToSave = url || headline || "[Skipped]";
    try {
      if (headline) {
        await api("/api/linkedin/paste", {
          method: "POST",
          body: JSON.stringify({ headline }),
        });
      }
      await api("/api/counsel/answer", {
        method: "POST",
        body: JSON.stringify({
          step: "linkedin",
          text: valueToSave,
          input_mode: "text",
        }),
      });

      setPersona((prev) => ({
        ...prev,
        linkedinUrl: valueToSave === "[Skipped]" ? undefined : valueToSave,
      }));

      setCurrentStage("target_jobs");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to save LinkedIn profile");
      }
    } finally {
      setSavingLinkedin(false);
    }
  }

  // --------------------------------------------------------------------------
  // STAGE 3: TARGET MARKET ROLES (SEARCH + DROPDOWN, MAX 3)
  // --------------------------------------------------------------------------
  function handleSelectRole(roleIdOrTitle: string) {
    setError(null);
    if (selectedRoleIds.includes(roleIdOrTitle)) return;
    if (selectedRoleIds.length >= 3) {
      setError("You can select up to a maximum of 3 target roles.");
      return;
    }
    const updated = [...selectedRoleIds, roleIdOrTitle];
    setSelectedRoleIds(updated);
    setRoleSearchQuery("");
    setIsRoleDropdownOpen(false);
  }

  function handleRemoveRole(roleIdOrTitle: string) {
    setSelectedRoleIds((prev) => prev.filter((r) => r !== roleIdOrTitle));
  }

  function handleMakePriority(roleIdOrTitle: string) {
    const filtered = selectedRoleIds.filter((r) => r !== roleIdOrTitle);
    setSelectedRoleIds([roleIdOrTitle, ...filtered]);
  }

  async function handleSaveTargetRoles() {
    if (selectedRoleIds.length === 0) {
      setError("Please select at least one target role from the market catalog.");
      return;
    }
    setError(null);
    setSavingRoles(true);
    try {
      const primaryRole = selectedRoleIds[0];

      // 1. Record target_work and priority_role in counsel sections
      await api("/api/counsel/answer", {
        method: "POST",
        body: JSON.stringify({
          step: "target_work",
          text: selectedRoleIds.join(", "),
          input_mode: "text",
        }),
      });
      await api("/api/counsel/answer", {
        method: "POST",
        body: JSON.stringify({
          step: "priority_role",
          text: primaryRole,
          input_mode: "text",
        }),
      });

      // 2. Save the candidate's exact selection last so it is what sticks
      await api("/api/roles", {
        method: "POST",
        body: JSON.stringify({
          role_ids: selectedRoleIds,
          mgmt_experience: false,
          priority_role_id: primaryRole,
        }),
      });

      const updatedPersona: PersonaState = {
        ...persona,
        targetRoles: selectedRoleIds,
        priorityRole: primaryRole,
      };
      setPersona(updatedPersona);

      setCurrentStage("live_chat");
      startLiveChatSession(updatedPersona);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to save target roles");
      }
    } finally {
      setSavingRoles(false);
    }
  }

  // --------------------------------------------------------------------------
  // STAGE 4: EXPERT COUNSELLOR DIAGNOSIS & PREFERENCES SECTION
  // --------------------------------------------------------------------------
  function startLiveChatSession(currentPersona: PersonaState, catalog: CatalogRole[] = catalogRoles) {
    if (chatMessages.length > 0) return;

    const primaryRole =
      currentPersona.priorityRole || currentPersona.targetRoles[0] || "Senior Software Engineer";
    const primaryTitle =
      catalog.find((r) => r.id === primaryRole)?.title ??
      primaryRole.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

    const initialGreeting =
      `Hello! I'm your AI Executive Career Counsellor.\n\n` +
      `I've analyzed your resume and market positioning for ${primaryTitle}. ` +
      `I have identified your best-fit jobs and calibrated your profile above.\n\n` +
      `Answer my questions above so I can score jobs properly, or ask me anything about your search below. When you are ready, click "Confirm & Scout My Jobs".`;

    setChatMessages([
      {
        id: "greeting-1",
        role: "assistant",
        content: initialGreeting,
        timestamp: "Just now",
      },
    ]);
  }

  async function handleSendChatMessage(overrideText?: string) {
    const text = (overrideText !== undefined ? overrideText : chatInputText).trim();
    if (!text || sendingChat) return;

    setError(null);
    setChatInputText("");
    setSendingChat(true);

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
      timestamp: "Just now",
      inputMode,
    };

    setChatMessages((prev) => [...prev, userMsg]);
    setIsAiTyping(true);

    try {
      const historyPayload = chatMessages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const contextPayload = {
        target_roles: persona.targetRoles,
        skills: persona.extractedSkills,
        linkedin: persona.linkedinUrl || "None",
      };

      const res = await api<{
        reply: string;
        detected_attributes: Record<string, any>;
        stage: string;
      }>("/api/counsel/chat", {
        method: "POST",
        body: JSON.stringify({
          message: text,
          history: historyPayload,
          context: contextPayload,
        }),
      });

      const assistantMsg: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: res.reply,
        timestamp: "Just now",
      };

      setChatMessages((prev) => [...prev, assistantMsg]);

      // What the counsellor picks up in conversation becomes a profile fact (and rescores jobs).
      const detected = res.detected_attributes || {};
      const facts: Record<string, unknown> = {};
      if (detected.management === true) facts.seniority = "Manager / Lead";
      if (detected.authorization === "Requires Visa Sponsorship") facts.needs_sponsorship = true;
      if (typeof detected.authorization === "string" && detected.authorization.startsWith("Authorized")) {
        facts.needs_sponsorship = false;
      }
      if (Object.keys(facts).length > 0) {
        await api("/api/profile/facts", { method: "PATCH", body: JSON.stringify(facts) }).catch(() => null);
        setFactsVersion((v) => v + 1);
      }
    } catch {
      const fallbackMsg: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content:
          "I've noted that! Your profile and target roles are well-calibrated. " +
          "You can adjust preferences anytime above or click 'Confirm & Scout My Jobs' to continue.",
        timestamp: "Just now",
      };
      setChatMessages((prev) => [...prev, fallbackMsg]);
    } finally {
      setSendingChat(false);
      setIsAiTyping(false);
    }
  }

  async function handleVoiceInput() {
    setError(null);
    setListening(true);
    try {
      const transcript = await listenOnce();
      setChatInputText(transcript);
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

  async function handleFinalizePersona() {
    setError(null);
    setFinalizingPersona(true);
    try {
      const { stage } = await api<{ stage: string }>("/api/counsel/finalize", { method: "POST" });
      window.location.assign(pageForStage(stage));
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to finalize candidate persona");
      }
    } finally {
      setFinalizingPersona(false);
    }
  }

  // Filter roles for the market catalog dropdown
  const filteredRoles = catalogRoles.filter((r) => {
    const q = roleSearchQuery.toLowerCase().trim();
    if (!q) return true;
    return (
      r.title.toLowerCase().includes(q) ||
      r.family.toLowerCase().includes(q) ||
      r.aliases?.some((a) => a.toLowerCase().includes(q))
    );
  });

  // Calculate top 3 recommended job diagnosis cards based on selections & resume
  const diagnosisRoles = selectedRoleIds;
  const hasResume = Boolean(uploadedResume) || resumeDone;

  return (
    <Shell title="Career Counsellor & Job Matching">
      <div className="space-y-6">
        {/* Onboarding Stepper Header with Direct Skip Action */}
        <div className="neo-raised p-5 rounded-2xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border border-white/80 bg-white/70 backdrop-blur-md shadow-md shadow-slate-200/50">
          <div className="flex items-center gap-3">
            <div className={`h-11 w-11 rounded-2xl text-white flex items-center justify-center font-bold text-lg shadow-md shrink-0 ${
              currentStage === "resume"
                ? "bg-gradient-to-br from-teal-600 via-teal-700 to-emerald-600 shadow-teal-700/20"
                : currentStage === "linkedin"
                ? "bg-gradient-to-br from-sky-600 via-cyan-600 to-blue-600 shadow-sky-700/20"
                : currentStage === "target_jobs"
                ? "bg-gradient-to-br from-amber-500 via-orange-500 to-amber-600 shadow-amber-700/20"
                : "bg-gradient-to-br from-emerald-600 via-teal-600 to-cyan-700 shadow-emerald-700/20"
            }`}>
              {currentStage === "resume" && "📄"}
              {currentStage === "linkedin" && "💼"}
              {currentStage === "target_jobs" && "🎯"}
              {currentStage === "live_chat" && "🚀"}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-wider text-teal-900">
                  Career Counsellor Engine
                </span>
              </div>
              <h2 className="text-sm font-bold text-ink">
                {currentStage === "resume" && "Step 1 of 4: Upload Resume (Required)"}
                {currentStage === "linkedin" && "Step 2 of 4: LinkedIn Profile (Optional)"}
                {currentStage === "target_jobs" && "Step 3 of 4: Target Market Roles (Max 3)"}
                {currentStage === "live_chat" && "Step 4 of 4: Expert Job Matches & Preferences"}
              </h2>
            </div>
          </div>

          {/* Stepper Navigation Pills & Immediate Skip Button */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setCurrentStage("resume")}
              className={`px-3 py-2 text-xs font-bold rounded-xl transition-all ${
                currentStage === "resume"
                  ? "neo-pressed text-teal-950 font-black border border-teal-500/50 bg-gradient-to-r from-teal-50 to-emerald-50 shadow-inner"
                  : hasResume
                  ? "bg-emerald-50/90 text-emerald-800 border border-emerald-300/80 hover:bg-emerald-100"
                  : "neo-raised text-muted hover:text-ink"
              }`}
            >
              1. Resume {hasResume && "✓"}
            </button>

            <button
              type="button"
              onClick={() => {
                if (hasResume) setCurrentStage("linkedin");
              }}
              disabled={!hasResume}
              className={`px-3 py-2 text-xs font-bold rounded-xl transition-all disabled:opacity-40 ${
                currentStage === "linkedin"
                  ? "neo-pressed text-sky-950 font-black border border-sky-500/50 bg-gradient-to-r from-sky-50 to-cyan-50 shadow-inner"
                  : persona.linkedinUrl
                  ? "bg-sky-50/90 text-sky-800 border border-sky-300/80 hover:bg-sky-100"
                  : "neo-raised text-muted hover:text-ink"
              }`}
            >
              2. LinkedIn {persona.linkedinUrl && "✓"}
            </button>

            <button
              type="button"
              onClick={() => {
                if (hasResume) setCurrentStage("target_jobs");
              }}
              disabled={!hasResume}
              className={`px-3 py-2 text-xs font-bold rounded-xl transition-all disabled:opacity-40 ${
                currentStage === "target_jobs"
                  ? "neo-pressed text-amber-950 font-black border border-amber-500/50 bg-gradient-to-r from-amber-50 to-orange-50 shadow-inner"
                  : selectedRoleIds.length > 0
                  ? "bg-amber-50/90 text-amber-800 border border-amber-300/80 hover:bg-amber-100"
                  : "neo-raised text-muted hover:text-ink"
              }`}
            >
              3. Target Roles ({selectedRoleIds.length}/3)
            </button>

            <button
              type="button"
              onClick={() => {
                if (hasResume && selectedRoleIds.length > 0) {
                  setCurrentStage("live_chat");
                  startLiveChatSession(persona);
                }
              }}
              disabled={!hasResume || selectedRoleIds.length === 0}
              className={`px-3 py-2 text-xs font-bold rounded-xl transition-all disabled:opacity-40 ${
                currentStage === "live_chat"
                  ? "neo-pressed text-teal-950 font-black border border-teal-500/50 bg-gradient-to-r from-teal-50 via-emerald-50 to-cyan-50 shadow-inner"
                  : "neo-raised text-muted hover:text-ink"
              }`}
            >
              4. Counselor & Matches
            </button>

          </div>
        </div>

        {error && (
          <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-medium flex items-center justify-between">
            <span>{error}</span>
            <button
              onClick={() => setError(null)}
              className="text-rose-600 hover:text-rose-900 font-bold ml-4"
            >
              ✕
            </button>
          </div>
        )}

        {/* ==================================================================== */}
        {/* SCREEN 1: UPLOAD RESUME (VERY FIRST THING)                            */}
        {/* ==================================================================== */}
        {loading && (
          <div className="neo-card p-10 text-center text-muted" role="status">
            <div className="inline-block h-6 w-6 rounded-full border-2 border-teal-600 border-t-transparent animate-spin" />
          </div>
        )}

        {!loading && currentStage === "resume" && (
          <div className="max-w-2xl mx-auto animate-chat-in">
            <div className="neo-card p-8 sm:p-10 space-y-6 text-center">
              <div className="space-y-2">
                <div className="mx-auto h-14 w-14 rounded-2xl bg-gradient-to-br from-teal-500 to-emerald-600 text-white flex items-center justify-center text-3xl shadow-lg shadow-teal-600/20 mb-2">
                  📄
                </div>
                <span className="badge-teal text-[10px] py-0.5 px-2.5 font-bold uppercase tracking-wider">
                  Step 1 of 4 • Resume Upload
                </span>
                <h3 className="text-2xl font-black text-ink tracking-tight">Upload Your Resume</h3>
                <p className="text-xs text-muted max-w-md mx-auto">
                  PDF format only (up to 10MB). Automatically extracted into your private candidate persona.
                </p>
              </div>

              {/* Interactive Dropzone */}
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
                className={`p-8 sm:p-10 rounded-2xl border-2 border-dashed transition-all duration-200 text-center space-y-4 ${
                  isDragging
                    ? "border-teal-500 bg-teal-50/80 scale-[1.01]"
                    : uploadedResume
                    ? "border-emerald-400 bg-emerald-50/30"
                    : "border-slate-300 hover:border-teal-400 bg-slate-50/50"
                }`}
              >
                <input
                  type="file"
                  id="resume-file-input"
                  accept=".pdf,application/pdf"
                  onChange={handleResumeChange}
                  disabled={uploadingResume}
                  className="hidden"
                />

                {!uploadedResume && !uploadingResume && (
                  <div className="space-y-4 py-4">
                    <div className="mx-auto h-16 w-16 rounded-full bg-teal-50 flex items-center justify-center text-teal-600 text-2xl border border-teal-200">
                      ☁️
                    </div>
                    <div>
                      <p className="text-sm font-bold text-ink">
                        Drag & drop your PDF resume here
                      </p>
                      <p className="text-xs text-muted mt-1">or browse from your device</p>
                    </div>
                    <label
                      htmlFor="resume-file-input"
                      className="btn-teal inline-flex items-center justify-center gap-2 px-8 py-3 text-xs font-bold uppercase tracking-wider cursor-pointer shadow-md hover:shadow-lg transition-all active:scale-[0.97]"
                    >
                      <span>Choose Resume PDF</span>
                    </label>
                  </div>
                )}

                {uploadingResume && (
                  <div className="p-8 rounded-xl bg-teal-50/80 border border-teal-200 flex flex-col items-center justify-center gap-3 text-teal-800">
                    <div className="h-8 w-8 rounded-full border-2 border-teal-600 border-t-transparent animate-spin" />
                    <p className="text-xs font-bold uppercase tracking-wider">
                      Parsing Skills & Scope with AI...
                    </p>
                  </div>
                )}

                {!uploadedResume && resumeDone && !uploadingResume && (
                  <p className="text-xs text-emerald-800 font-semibold">
                    ✓ Resume already on file. Upload a new PDF to replace it.
                  </p>
                )}

                {uploadedResume && !uploadingResume && (
                  <div className="space-y-4 text-left">
                    <div className="p-4 rounded-xl bg-emerald-50/90 border border-emerald-300 flex items-center justify-between gap-3 shadow-xs">
                      <div className="flex items-center gap-3">
                        <span className="h-9 w-9 rounded-xl bg-emerald-500 text-white flex items-center justify-center font-bold text-base shadow-sm">
                          ✓
                        </span>
                        <div>
                          <p className="text-xs font-bold text-emerald-950 truncate max-w-[280px]">
                            {uploadedResume.filename}
                          </p>
                          <p className="text-[11px] text-emerald-800 font-medium">
                            {uploadedResume.skillsCount} technical skills extracted
                          </p>
                        </div>
                      </div>
                      <label
                        htmlFor="resume-file-input"
                        className="text-xs font-bold text-teal-700 hover:text-teal-900 underline cursor-pointer shrink-0"
                      >
                        Change PDF
                      </label>
                    </div>

                    {uploadedResume.extractedSkills.length > 0 && (
                      <div className="space-y-2.5 pt-2">
                        <div>
                          <p className="text-sm font-bold text-ink">Which of these have you really used?</p>
                          <p className="text-[11px] text-muted">
                            Tap to confirm. Only confirmed skills count fully when we score jobs — unconfirmed ones count half.
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-1.5 max-h-40 overflow-y-auto pr-1">
                          {uploadedResume.extractedSkills.map((skill) => {
                            const on = confirmedSkills.includes(skill);
                            return (
                              <button
                                key={skill}
                                type="button"
                                aria-pressed={on}
                                disabled={skillsSaved}
                                onClick={() =>
                                  setConfirmedSkills((prev) => (on ? prev.filter((x) => x !== skill) : [...prev, skill]))
                                }
                                className={`px-2.5 py-1.5 text-xs font-bold rounded-lg border transition-colors ${
                                  on
                                    ? "bg-teal-600 text-white border-teal-600"
                                    : "bg-white/80 text-ink border-slate-200 hover:border-teal-400"
                                }`}
                              >
                                {on ? "✓ " : ""}
                                {skill}
                              </button>
                            );
                          })}
                        </div>
                        {skillsSaved ? (
                          <p className="text-xs font-semibold text-teal-800">
                            ✓ {confirmedSkills.length} skill{confirmedSkills.length === 1 ? "" : "s"} confirmed.
                          </p>
                        ) : (
                          <button
                            type="button"
                            disabled={confirmedSkills.length === 0 || savingSkills}
                            onClick={handleConfirmResumeSkills}
                            className="btn-teal px-4 py-2 text-xs disabled:opacity-40"
                          >
                            {savingSkills ? "Saving..." : `Confirm ${confirmedSkills.length || ""} skill${confirmedSkills.length === 1 ? "" : "s"}`}
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {hasResume && (
                <div className="pt-2 flex justify-end">
                  <button
                    type="button"
                    onClick={handleContinueFromResume}
                    className="btn-teal w-full sm:w-auto px-8 py-3 text-xs font-bold uppercase tracking-wider shadow-md active:scale-[0.97] flex items-center justify-center gap-2"
                  >
                    <span>Continue to LinkedIn Profile →</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ==================================================================== */}
        {/* SCREEN 2: ADD LINKEDIN PROFILE (SKIPPABLE)                           */}
        {/* ==================================================================== */}
        {!loading && currentStage === "linkedin" && (
          <div className="max-w-2xl mx-auto animate-chat-in">
            <div className="neo-card p-8 sm:p-10 space-y-6 text-center">
              <div className="space-y-2">
                <div className="mx-auto h-14 w-14 rounded-2xl bg-gradient-to-br from-sky-500 via-cyan-600 to-blue-600 text-white flex items-center justify-center text-3xl shadow-lg shadow-sky-600/20 mb-2">
                  💼
                </div>
                <span className="badge-sky text-[10px] py-0.5 px-2.5 font-bold uppercase tracking-wider">
                  Step 2 of 4 • Public Profile
                </span>
                <h3 className="text-2xl font-black text-ink tracking-tight">Add Your LinkedIn Profile</h3>
                <p className="text-xs text-muted max-w-md mx-auto">
                  Calibrate company pedigree and public presence (optional). If you don&apos;t use LinkedIn, you can skip.
                </p>
              </div>

              <div className="space-y-4 max-w-lg mx-auto text-left">
                <input
                  type="url"
                  value={linkedinInput}
                  onChange={(e) => setLinkedinInput(e.target.value)}
                  placeholder="https://www.linkedin.com/in/your-profile"
                  aria-label="LinkedIn profile URL"
                  className="neo-inset w-full px-4 py-3.5 text-xs text-ink bg-transparent focus:outline-none focus:ring-2 focus:ring-sky-500/30 rounded-xl"
                />
                <input
                  type="text"
                  value={linkedinHeadline}
                  onChange={(e) => setLinkedinHeadline(e.target.value)}
                  placeholder="Your LinkedIn headline, e.g. Senior Backend Engineer | Distributed Systems"
                  aria-label="LinkedIn headline"
                  className="neo-inset w-full px-4 py-3.5 text-xs text-ink bg-transparent focus:outline-none focus:ring-2 focus:ring-sky-500/30 rounded-xl"
                />
                <p className="text-[11px] text-muted">
                  The headline is what we check against your target roles for readiness.
                </p>
              </div>

              <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-4 border-t border-slate-200/60 max-w-lg mx-auto">
                <button
                  type="button"
                  onClick={() => handleSaveLinkedin(true)}
                  disabled={savingLinkedin}
                  className="w-full sm:w-auto neo-raised px-6 py-3 text-xs font-semibold text-muted hover:text-ink rounded-xl active:scale-[0.97]"
                >
                  Skip for now →
                </button>

                <button
                  type="button"
                  onClick={() => handleSaveLinkedin(false)}
                  disabled={savingLinkedin || (!linkedinInput.trim() && !linkedinHeadline.trim())}
                  className="w-full sm:w-auto btn-sky px-8 py-3 text-xs font-bold uppercase tracking-wider disabled:opacity-50 shadow-md active:scale-[0.97]"
                >
                  {savingLinkedin ? "Saving..." : "Save & Continue →"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ==================================================================== */}
        {/* SCREEN 3: TARGET MARKET ROLES (SEARCH BAR + DROPDOWN, MAX 3)         */}
        {/* ==================================================================== */}
        {!loading && currentStage === "target_jobs" && (
          <div className="max-w-3xl mx-auto animate-chat-in">
            <div className="neo-card p-8 sm:p-10 space-y-6">
              <div className="text-center space-y-2">
                <div className="mx-auto h-14 w-14 rounded-2xl bg-gradient-to-br from-amber-500 via-orange-500 to-amber-600 text-white flex items-center justify-center text-3xl shadow-lg shadow-amber-600/20 mb-2">
                  🎯
                </div>
                <span className="badge-amber text-[10px] py-0.5 px-2.5 font-bold uppercase tracking-wider">
                  Step 3 of 4 • Target Market Roles
                </span>
                <h3 className="text-2xl font-black text-ink tracking-tight">
                  What kind of job are you looking for?
                </h3>
                <p className="text-xs text-muted max-w-md mx-auto">
                  Select up to 3 target market roles. Your first selection will be your #1 Priority Role.
                </p>
              </div>

              {/* 3 Visual Role Slots */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {[0, 1, 2].map((slotIdx) => {
                  const roleId = selectedRoleIds[slotIdx];
                  const catalogMatch = catalogRoles.find((r) => r.id === roleId);
                  const title =
                    catalogMatch?.title ||
                    (roleId ? roleId.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) : null);
                  const isPriority = slotIdx === 0;

                  return (
                    <div
                      key={slotIdx}
                      className={`p-4 rounded-xl border transition-all min-h-[90px] flex flex-col justify-between ${
                        roleId
                          ? isPriority
                            ? "bg-gradient-to-br from-amber-50/90 to-orange-50/40 border-amber-400/90 shadow-sm"
                            : "bg-white/90 border-teal-300/80 shadow-xs"
                          : "border-dashed border-slate-300 bg-slate-50/40 items-center justify-center text-center text-muted"
                      }`}
                    >
                      {roleId ? (
                        <>
                          <div className="flex items-start justify-between gap-1">
                            <span
                              className={`text-[10px] font-bold uppercase py-0.5 px-2 rounded-md ${
                                isPriority
                                  ? "bg-amber-100 text-amber-900 border border-amber-300"
                                  : "bg-teal-100 text-teal-900 border border-teal-300"
                              }`}
                            >
                              {isPriority ? "⭐ #1 Priority" : `Slot ${slotIdx + 1}`}
                            </span>
                            <button
                              type="button"
                              onClick={() => handleRemoveRole(roleId)}
                              className="text-muted hover:text-rose-600 text-xs font-bold px-1"
                            >
                              ✕
                            </button>
                          </div>
                          <p className="text-xs font-bold text-ink mt-2 leading-snug line-clamp-2">
                            {title}
                          </p>
                        </>
                      ) : (
                        <div className="py-2">
                          <span className="text-[11px] font-medium text-slate-400">
                            {slotIdx === 0 ? "+ Slot 1 (Priority)" : `+ Slot ${slotIdx + 1}`}
                          </span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Search Bar + Dropdown */}
              <div className="relative">
                <input
                  ref={searchInputRef}
                  type="text"
                  value={roleSearchQuery}
                  onFocus={() => setIsRoleDropdownOpen(true)}
                  onChange={(e) => {
                    setRoleSearchQuery(e.target.value);
                    setIsRoleDropdownOpen(true);
                  }}
                  placeholder="Type to search roles (e.g. Backend, Full Stack, AI Systems, Manager)..."
                  className="neo-inset w-full px-4 py-3 text-xs text-ink bg-transparent focus:outline-none focus:ring-2 focus:ring-teal-500/30 rounded-xl"
                />

                {roleSearchQuery && (
                  <button
                    type="button"
                    onClick={() => {
                      setRoleSearchQuery("");
                      setIsRoleDropdownOpen(false);
                    }}
                    className="absolute right-3 top-3 text-xs text-muted hover:text-ink"
                  >
                    ✕
                  </button>
                )}

                {/* Dropdown Menu */}
                {isRoleDropdownOpen && (
                  <div className="absolute z-20 top-full left-0 right-0 mt-1 max-h-60 overflow-y-auto neo-raised bg-white rounded-xl shadow-xl border border-slate-200 divide-y divide-slate-100">
                    {filteredRoles.map((r) => {
                      const isSelected = selectedRoleIds.includes(r.id);
                      return (
                        <button
                          key={r.id}
                          type="button"
                          onClick={() => handleSelectRole(r.id)}
                          disabled={isSelected || selectedRoleIds.length >= 3}
                          className={`w-full px-4 py-2.5 text-left text-xs flex items-center justify-between hover:bg-teal-50/60 transition-all ${
                            isSelected ? "opacity-50 bg-slate-50 cursor-not-allowed" : ""
                          }`}
                        >
                          <div>
                            <p className="font-bold text-ink">{r.title}</p>
                            <p className="text-[10px] text-muted">{r.family}</p>
                          </div>
                          <span className="text-[11px] font-semibold text-teal-700">
                            {isSelected ? "Selected ✓" : "+ Add"}
                          </span>
                        </button>
                      );
                    })}

                    {/* Add Custom Title if typed */}
                    {roleSearchQuery.trim() &&
                      !catalogRoles.some(
                        (r) => r.title.toLowerCase() === roleSearchQuery.trim().toLowerCase()
                      ) && (
                        <button
                          type="button"
                          onClick={() => handleSelectRole(roleSearchQuery.trim())}
                          disabled={selectedRoleIds.length >= 3}
                          className="w-full px-4 py-2.5 text-left text-xs font-bold text-teal-800 bg-teal-50/80 hover:bg-teal-100 flex items-center justify-between"
                        >
                          <span>+ Add custom role: &quot;{roleSearchQuery.trim()}&quot;</span>
                          <span className="text-[10px] uppercase font-bold text-teal-900">Custom</span>
                        </button>
                      )}
                  </div>
                )}
              </div>

              {/* Quick Popular Suggestions */}
              <div className="space-y-2">
                <span className="text-[11px] font-bold uppercase tracking-wider text-muted block">
                  Quick Add In-Demand Tech Roles:
                </span>
                <div className="flex flex-wrap gap-2">
                  {[
                    { title: "Staff Backend Engineer", style: "bg-teal-50 text-teal-900 border-teal-300 hover:bg-teal-100" },
                    { title: "Full Stack Engineer", style: "bg-sky-50 text-sky-900 border-sky-300 hover:bg-sky-100" },
                    { title: "Senior Software Engineer", style: "bg-blue-50 text-blue-900 border-blue-300 hover:bg-blue-100" },
                    { title: "AI Systems Engineer", style: "bg-emerald-50 text-emerald-900 border-emerald-300 hover:bg-emerald-100" },
                    { title: "Engineering Manager", style: "bg-amber-50 text-amber-900 border-amber-300 hover:bg-amber-100" },
                    { title: "Platform / DevOps Engineer", style: "bg-orange-50 text-orange-900 border-orange-300 hover:bg-orange-100" },
                  ].map((preset) => {
                    const presetLower = preset.title.toLowerCase();
                    const matched = catalogRoles.find(
                      (r) =>
                        r.title.toLowerCase() === presetLower ||
                        r.aliases?.some((a) => a.toLowerCase() === presetLower)
                    );
                    const roleId = matched ? matched.id : preset.title;
                    const isSelected = selectedRoleIds.includes(roleId);
                    return (
                      <button
                        key={preset.title}
                        type="button"
                        onClick={() => handleSelectRole(roleId)}
                        disabled={isSelected || selectedRoleIds.length >= 3}
                        className={`px-3 py-1.5 text-xs font-semibold rounded-xl border transition-all ${
                          isSelected
                            ? "opacity-40 line-through bg-slate-100 border-slate-200 text-muted"
                            : `${preset.style} shadow-xs hover:-translate-y-0.5`
                        }`}
                      >
                        {isSelected ? `✓ ${preset.title}` : `+ ${preset.title}`}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="flex justify-end pt-4 border-t border-slate-200/80">
                <button
                  type="button"
                  onClick={handleSaveTargetRoles}
                  disabled={selectedRoleIds.length === 0 || savingRoles}
                  className="btn-teal w-full sm:w-auto px-8 py-3 text-xs font-bold uppercase tracking-wider disabled:opacity-50 shadow-md active:scale-[0.97] flex items-center justify-center gap-2"
                >
                  <span>
                    {savingRoles ? "Saving Roles..." : "Proceed to Career Counselor →"}
                  </span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ==================================================================== */}
        {/* SCREEN 4: EXPERT CAREER COUNSELOR & LIVE PERSONA ADVICE              */}
        {/* ==================================================================== */}
        {!loading && currentStage === "live_chat" && (
          <div className="max-w-4xl mx-auto space-y-6 animate-chat-in">
            {/* Top Bar with Instant Skip */}
            <div className="neo-card p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border border-teal-500/30 bg-gradient-to-r from-teal-50/50 via-white to-sky-50/40">
              <div className="flex items-center gap-3">
                <div className="h-12 w-12 rounded-2xl bg-gradient-to-br from-teal-600 via-emerald-600 to-sky-600 text-white flex items-center justify-center text-2xl shadow-md">
                  🧭
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="badge-teal text-[10px] py-0.5 px-2 font-bold uppercase tracking-wider">
                      Step 4 of 4 • Career Counselor
                    </span>
                    <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                  </div>
                  <h3 className="text-lg font-bold text-ink">Personalized Job Matches & Advisory</h3>
                </div>
              </div>

              <button
                type="button"
                onClick={handleFinalizePersona}
                disabled={finalizingPersona}
                className="btn-amber w-full sm:w-auto px-6 py-2.5 text-xs font-bold uppercase tracking-wider shadow-md active:scale-[0.97] flex items-center justify-center gap-2 shrink-0"
              >
                <span>{finalizingPersona ? "Finalizing..." : "Skip Chat & Scout Jobs ⚡ →"}</span>
              </button>
            </div>

            {/* Top 3 Diagnosed Market Job Fits */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {diagnosisRoles.slice(0, 3).map((rId, idx) => {
                const match = catalogRoles.find((r) => r.id === rId);
                const title =
                  match?.title || rId.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
                const roleRank =
                  idx === 0 ? "Primary Target" : idx === 1 ? "Secondary" : "Growth Opportunity";

                const tierStyles = [
                  { border: "border-emerald-500/70 bg-gradient-to-br from-emerald-50/70 via-white to-teal-50/40", badge: "badge-emerald" },
                  { border: "border-sky-500/70 bg-gradient-to-br from-sky-50/70 via-white to-cyan-50/40", badge: "badge-sky" },
                  { border: "border-amber-500/70 bg-gradient-to-br from-amber-50/70 via-white to-orange-50/40", badge: "badge-amber" },
                ];
                const tier = tierStyles[idx] || tierStyles[0];

                return (
                  <div
                    key={rId}
                    className={`p-5 rounded-2xl space-y-2.5 border shadow-sm transition-all ${tier.border}`}
                  >
                    <div className="text-[10px]">
                      <span className={`${tier.badge} font-bold py-0.5 px-2`}>{roleRank}</span>
                    </div>

                    <h4 className="text-sm font-black text-ink leading-snug">{title}</h4>
                    {match?.baseline_skills && (
                      <p className="text-[11px] text-muted pt-1 border-t border-slate-200/50">
                        Core skills: {match.baseline_skills.join(", ")}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>

            {/* The counsellor collects job-search facts one question at a time */}
            <FactQuestion key={factsVersion} />

            {/* Live Interactive Counselor Chat */}
            <div className="neo-card p-6 space-y-4 border border-teal-500/20 bg-white/95">
              <div className="flex items-center justify-between border-b border-slate-200/60 pb-3">
                <div className="flex items-center gap-2">
                  <div className="h-8 w-8 rounded-xl bg-teal-600 text-white flex items-center justify-center font-bold text-xs shadow-sm">
                    AI
                  </div>
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-wider text-ink">
                      Career Counselor Session
                    </h4>
                    <p className="text-[11px] text-muted">
                      Calibrating company tier, team scope, and search boundaries.
                    </p>
                  </div>
                </div>
                <span className="badge-teal text-[10px] py-0.5 px-2">Live Counselor</span>
              </div>

              {/* Chat Thread */}
              <div className="max-h-80 overflow-y-auto space-y-3 p-4 rounded-xl bg-slate-50/70 border border-slate-200/60">
                {chatMessages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex items-start gap-2.5 ${
                      msg.role === "user" ? "justify-end ml-auto max-w-md" : "max-w-md"
                    }`}
                  >
                    {msg.role === "assistant" && (
                      <div className="h-7 w-7 rounded-lg bg-teal-600 text-white flex items-center justify-center font-bold text-[10px] shrink-0 mt-0.5 shadow-xs">
                        AI
                      </div>
                    )}
                    <div
                      className={`p-3.5 rounded-xl text-xs leading-relaxed ${
                        msg.role === "user"
                          ? "bg-teal-700 text-white shadow-xs"
                          : "bg-white text-ink border border-slate-200/80 shadow-xs"
                      }`}
                    >
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  </div>
                ))}
                {isAiTyping && (
                  <div className="text-[11px] text-teal-700 animate-pulse pl-9 flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-teal-600 animate-ping" />
                    <span>Counselor is typing strategic guidance...</span>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              {/* Quick Reply Suggestion Chips */}
              <div className="flex flex-wrap gap-2 pt-1">
                {[
                  { text: "🚀 Fast-paced VC Startup", style: "bg-sky-50 text-sky-900 border-sky-300 hover:bg-sky-100" },
                  { text: "🏢 High-scale Public Tech", style: "bg-emerald-50 text-emerald-900 border-emerald-300 hover:bg-emerald-100" },
                  { text: "🌍 100% Async Remote-First", style: "bg-teal-50 text-teal-900 border-teal-300 hover:bg-teal-100" },
                  { text: "💰 Maximize Base Salary & Equity", style: "bg-amber-50 text-amber-900 border-amber-300 hover:bg-amber-100" },
                ].map((chip) => (
                  <button
                    key={chip.text}
                    type="button"
                    onClick={() => handleSendChatMessage(chip.text)}
                    className={`px-3 py-1.5 text-[11px] font-bold rounded-xl border shadow-xs transition-all active:scale-[0.97] ${chip.style}`}
                  >
                    {chip.text}
                  </button>
                ))}
              </div>

              {/* Chat Input Bar */}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSendChatMessage();
                }}
                className="flex items-center gap-2 pt-2"
              >
                <input
                  type="text"
                  value={chatInputText}
                  onChange={(e) => setChatInputText(e.target.value)}
                  placeholder="Tell counselor about your ideal role, culture, or compensation..."
                  className="neo-inset flex-1 px-4 py-3 text-xs text-ink bg-transparent focus:outline-none focus:ring-2 focus:ring-teal-500/30 rounded-xl"
                />

                <button
                  type="button"
                  onClick={handleVoiceInput}
                  disabled={listening || sendingChat}
                  className={`px-3 py-3 text-xs rounded-xl flex items-center justify-center transition-all ${
                    listening ? "bg-rose-100 text-rose-700 animate-pulse" : "neo-raised text-ink hover:text-teal-700"
                  }`}
                  title="Dictate via microphone"
                >
                  🎙️
                </button>

                <button
                  type="submit"
                  disabled={sendingChat || !chatInputText.trim()}
                  className="btn-teal px-6 py-3 text-xs font-bold uppercase tracking-wider disabled:opacity-50 active:scale-[0.97]"
                >
                  {sendingChat ? "Sending..." : "Send →"}
                </button>
              </form>

              {/* Bottom Confirm Action */}
              <div className="pt-4 border-t border-slate-200/70 flex flex-col sm:flex-row items-center justify-between gap-4">
                <p className="text-xs text-muted">
                  Scout has already started searching for these roles. Confirm to see your matches.
                </p>

                <button
                  type="button"
                  onClick={handleFinalizePersona}
                  disabled={finalizingPersona}
                  className="btn-teal w-full sm:w-auto px-8 py-3 text-xs font-bold uppercase tracking-wider shadow-md active:scale-[0.97]"
                >
                  {finalizingPersona
                    ? "Launching Scout..."
                    : "Confirm & Scout My Jobs →"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Shell>
  );
}

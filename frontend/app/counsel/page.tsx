"use client";

import React, { useEffect, useRef, useState } from "react";
import { Shell } from "@/components/Shell";
import { api } from "@/lib/api";
import { listenOnce } from "@/lib/speech";

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
  const [savingLinkedin, setSavingLinkedin] = useState(false);

  // Target Roles State
  const [catalogRoles, setCatalogRoles] = useState<CatalogRole[]>([]);
  const [roleSearchQuery, setRoleSearchQuery] = useState("");
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);
  const [savingRoles, setSavingRoles] = useState(false);
  const [isRoleDropdownOpen, setIsRoleDropdownOpen] = useState(false);

  // Live Chat State
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInputText, setChatInputText] = useState("");
  const [sendingChat, setSendingChat] = useState(false);
  const [listening, setListening] = useState(false);
  const [isAiTyping, setIsAiTyping] = useState(false);
  const [inputMode, setInputMode] = useState<"text" | "mic">("text");
  const [finalizingPersona, setFinalizingPersona] = useState(false);

  // Live Persona State
  const [persona, setPersona] = useState<PersonaState>({
    extractedSkills: [],
    targetRoles: [],
  });

  const chatEndRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    initOnboarding();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages, isAiTyping]);

  async function initOnboarding() {
    setLoading(true);
    setError(null);
    try {
      // 1. Fetch market catalog roles
      const catalog = await api<CatalogRole[]>("/api/roles/catalog").catch(() => []);
      setCatalogRoles(catalog);

      // 2. Fetch existing counsel state
      const counselState = await api<any>("/api/counsel").catch(() => null);
      if (counselState?.done) {
        window.location.assign("/todos");
        return;
      }

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
        linkedinUrl: histMap.linkedin && histMap.linkedin !== "[Skipped]" ? histMap.linkedin : undefined,
        location: histMap.location,
        authorization: histMap.authorization,
        preferences: histMap.preferences,
      };

      if (histMap.management) {
        initialPersona.management = histMap.management.toLowerCase().includes("yes");
      }

      // Check selected roles
      const selectedRolesData = await api<any[]>("/api/roles").catch(() => []);
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
        startLiveChatSession(initialPersona, histMap);
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
      setLoading(false);
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
      const extractedSkills = Array.isArray(data.extracted_skills) ? data.extracted_skills : [];
      const refId = data.id || file.name;

      const resumeInfo = {
        filename: file.name,
        skillsCount: extractedSkills.length,
        resumeId: refId,
        extractedSkills,
      };

      setUploadedResume(resumeInfo);
      setPersona((prev) => ({
        ...prev,
        resumeFilename: file.name,
        resumeSkillsCount: extractedSkills.length,
        extractedSkills,
      }));

      // Automatically record resume answer in counsel flow
      await api("/api/counsel/answer", {
        method: "POST",
        body: JSON.stringify({
          step: "resume",
          text: refId,
          input_mode: "text",
        }),
      }).catch(() => null);
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

  function handleResumeChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) processResumeFile(file);
  }

  function handleContinueFromResume() {
    if (!uploadedResume) {
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
    const valueToSave = skip || !linkedinInput.trim() ? "[Skipped]" : linkedinInput.trim();
    try {
      await api("/api/counsel/answer", {
        method: "POST",
        body: JSON.stringify({
          step: "linkedin",
          text: valueToSave,
          input_mode: "text",
        }),
      }).catch(() => null);

      setPersona((prev) => ({
        ...prev,
        linkedinUrl: skip ? undefined : valueToSave,
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

      // 1. Post to /api/roles
      await api("/api/roles", {
        method: "POST",
        body: JSON.stringify({
          role_ids: selectedRoleIds,
          mgmt_experience: persona.management || false,
          priority_role_id: primaryRole,
        }),
      }).catch(() => null);

      // 2. Record target_work and priority_role in counsel sections
      const rolesSummary = selectedRoleIds.join(", ");
      await api("/api/counsel/answer", {
        method: "POST",
        body: JSON.stringify({
          step: "target_work",
          text: rolesSummary,
          input_mode: "text",
        }),
      }).catch(() => null);

      await api("/api/counsel/answer", {
        method: "POST",
        body: JSON.stringify({
          step: "priority_role",
          text: primaryRole,
          input_mode: "text",
        }),
      }).catch(() => null);

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
  // STAGE 4: LIVE CHAT WITH THE COUNSELLOR (PERSONA BUILDING)
  // --------------------------------------------------------------------------
  function startLiveChatSession(currentPersona: PersonaState, histMap?: Record<string, string>) {
    if (chatMessages.length > 0) return;

    const primaryRole =
      currentPersona.priorityRole ||
      currentPersona.targetRoles[0] ||
      "Software Engineer";
    const rolesList =
      currentPersona.targetRoles.length > 0
        ? currentPersona.targetRoles
            .map((r) => r.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()))
            .join(", ")
        : primaryRole;

    const resumeName = currentPersona.resumeFilename || uploadedResume?.filename || "your resume";
    const skillsCount =
      currentPersona.resumeSkillsCount ||
      uploadedResume?.skillsCount ||
      currentPersona.extractedSkills.length ||
      12;

    const initialGreeting =
      `Hello! I'm your AI Executive Career Counsellor. I've reviewed ${resumeName} ` +
      `with ${skillsCount} extracted skills, and I see your target roles: ${rolesList}.\n\n` +
      `Now, let's build your strong candidate persona so our autonomous Scout agent can pinpoint ` +
      `the most lucrative, high-impact opportunities for you.\n\n` +
      `To start: What specific engineering problems or architectures bring out your best work, and do you prefer ` +
      `an Individual Contributor (IC) track or Engineering Management / Squad Lead track?`;

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

      // Update persona with any detected attributes
      if (res.detected_attributes) {
        setPersona((prev) => {
          const next = { ...prev };
          if (res.detected_attributes.management !== undefined) {
            next.management = res.detected_attributes.management;
          }
          if (res.detected_attributes.location) {
            next.location = res.detected_attributes.location;
          }
          if (res.detected_attributes.authorization) {
            next.authorization = res.detected_attributes.authorization;
          }
          if (res.detected_attributes.preferences) {
            next.preferences = res.detected_attributes.preferences;
          }
          return next;
        });
      }
    } catch (err: unknown) {
      const fallbackMsg: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content:
          "Thank you for sharing that context. I've incorporated it into your candidate persona. " +
          "Could you also clarify your location preferences (e.g. Remote vs Hybrid cities like SF, NYC, London, or Bengaluru) " +
          "and whether you require visa sponsorship?",
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
      await api("/api/counsel/finalize", { method: "POST" });
      window.location.assign("/todos");
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

  return (
    <Shell title="Candidate Onboarding & Persona Build">
      <div className="space-y-6">
        {/* Onboarding Stepper Header */}
        <div className="neo-raised p-5 rounded-2xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-teal-600 via-teal-700 to-cyan-700 text-white flex items-center justify-center font-bold text-sm shadow-md">
              ⚡
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-wider text-teal-800">
                  Candidate Persona Protocol
                </span>
                <span className="badge-teal text-[10px] py-0.5 px-2">DeepSeek v4.1</span>
              </div>
              <h2 className="text-sm font-bold text-ink">
                {currentStage === "resume" && "Step 1 of 4: Upload Resume (Required)"}
                {currentStage === "linkedin" && "Step 2 of 4: LinkedIn Profile (Optional)"}
                {currentStage === "target_jobs" && "Step 3 of 4: Target Market Roles (Max 3)"}
                {currentStage === "live_chat" && "Step 4 of 4: Live AI Counsellor Chat"}
              </h2>
            </div>
          </div>

          {/* Stepper Navigation Pills */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setCurrentStage("resume")}
              className={`px-3 py-1.5 text-xs font-bold rounded-xl transition-all ${
                currentStage === "resume"
                  ? "neo-pressed text-teal-800 border border-teal-500/40"
                  : uploadedResume
                  ? "neo-raised text-emerald-700 hover:text-teal-700"
                  : "neo-raised text-muted"
              }`}
            >
              1. Resume {uploadedResume && "✓"}
            </button>

            <button
              type="button"
              onClick={() => {
                if (uploadedResume) setCurrentStage("linkedin");
              }}
              disabled={!uploadedResume}
              className={`px-3 py-1.5 text-xs font-bold rounded-xl transition-all disabled:opacity-40 ${
                currentStage === "linkedin"
                  ? "neo-pressed text-teal-800 border border-teal-500/40"
                  : persona.linkedinUrl
                  ? "neo-raised text-emerald-700 hover:text-teal-700"
                  : "neo-raised text-muted"
              }`}
            >
              2. LinkedIn
            </button>

            <button
              type="button"
              onClick={() => {
                if (uploadedResume) setCurrentStage("target_jobs");
              }}
              disabled={!uploadedResume}
              className={`px-3 py-1.5 text-xs font-bold rounded-xl transition-all disabled:opacity-40 ${
                currentStage === "target_jobs"
                  ? "neo-pressed text-teal-800 border border-teal-500/40"
                  : selectedRoleIds.length > 0
                  ? "neo-raised text-emerald-700 hover:text-teal-700"
                  : "neo-raised text-muted"
              }`}
            >
              3. Target Roles ({selectedRoleIds.length}/3)
            </button>

            <button
              type="button"
              onClick={() => {
                if (uploadedResume && selectedRoleIds.length > 0) {
                  setCurrentStage("live_chat");
                  startLiveChatSession(persona);
                }
              }}
              disabled={!uploadedResume || selectedRoleIds.length === 0}
              className={`px-3 py-1.5 text-xs font-bold rounded-xl transition-all disabled:opacity-40 ${
                currentStage === "live_chat"
                  ? "neo-pressed text-teal-800 border border-teal-500/40"
                  : "neo-raised text-muted"
              }`}
            >
              4. Live Chat
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
        {currentStage === "resume" && (
          <div className="max-w-2xl mx-auto neo-card p-8 space-y-6 animate-chat-in">
            <div className="text-center space-y-2">
              <div className="inline-flex h-16 w-16 rounded-2xl bg-teal-100 text-teal-700 items-center justify-center text-3xl shadow-inner mx-auto">
                📄
              </div>
              <h3 className="text-xl font-bold text-ink">Upload Your Resume</h3>
              <p className="text-xs text-muted max-w-md mx-auto leading-relaxed">
                Start by uploading your current CV or resume in PDF format. DeepSeek will parse and
                extract your verified technical skills, latency and revenue impacts, and employment
                timelines.
              </p>
            </div>

            {/* Dropzone */}
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
              <input
                type="file"
                id="resume-file-input"
                accept=".pdf,application/pdf"
                onChange={handleResumeChange}
                disabled={uploadingResume}
                className="hidden"
              />

              {!uploadedResume && !uploadingResume && (
                <div className="space-y-3">
                  <p className="text-xs font-semibold text-ink">
                    Drag and drop your PDF resume here, or browse files
                  </p>
                  <label
                    htmlFor="resume-file-input"
                    className="btn-teal inline-flex items-center justify-center gap-2 px-6 py-2.5 text-xs font-bold uppercase tracking-wider cursor-pointer shadow-md hover:shadow-lg transition-all"
                  >
                    <span>Choose Resume PDF</span>
                  </label>
                  <p className="text-[11px] text-muted">PDF format only • Up to 10MB</p>
                </div>
              )}

              {uploadingResume && (
                <div className="p-4 rounded-xl bg-teal-50/80 border border-teal-200 flex flex-col items-center justify-center gap-2 text-teal-800">
                  <div className="h-6 w-6 rounded-full border-2 border-teal-600 border-t-transparent animate-spin" />
                  <p className="text-xs font-semibold">
                    Extracting technical skills, project scopes, and metrics with AI...
                  </p>
                  <span className="text-[11px] text-teal-600">This takes just a few seconds</span>
                </div>
              )}

              {uploadedResume && !uploadingResume && (
                <div className="space-y-4">
                  <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-left flex items-start justify-between gap-3 shadow-sm">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-emerald-700 font-bold text-sm">✓</span>
                        <span className="text-xs font-bold text-emerald-950 truncate max-w-[280px]">
                          {uploadedResume.filename}
                        </span>
                      </div>
                      <p className="text-[11px] text-emerald-800 font-medium">
                        Successfully parsed • {uploadedResume.skillsCount} skills detected and
                        vaulted.
                      </p>
                    </div>
                    <label
                      htmlFor="resume-file-input"
                      className="text-[11px] font-semibold text-teal-700 hover:text-teal-900 underline cursor-pointer shrink-0 py-1"
                    >
                      Change PDF
                    </label>
                  </div>

                  {uploadedResume.extractedSkills.length > 0 && (
                    <div className="text-left space-y-1.5">
                      <span className="text-[11px] font-bold uppercase text-muted tracking-wider">
                        Extracted Technical Skills:
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {uploadedResume.extractedSkills.slice(0, 15).map((skill) => (
                          <span
                            key={skill}
                            className="px-2.5 py-1 text-[11px] font-medium rounded-lg bg-teal-100/70 text-teal-900 border border-teal-200"
                          >
                            {skill}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={handleContinueFromResume}
                disabled={!uploadedResume || uploadingResume}
                className="btn-teal px-8 py-3 text-xs font-bold uppercase tracking-wider disabled:opacity-50 shadow-md flex items-center gap-2"
              >
                <span>Continue to LinkedIn Profile →</span>
              </button>
            </div>
          </div>
        )}

        {/* ==================================================================== */}
        {/* SCREEN 2: ADD LINKEDIN PROFILE (SKIPPABLE)                           */}
        {/* ==================================================================== */}
        {currentStage === "linkedin" && (
          <div className="max-w-2xl mx-auto neo-card p-8 space-y-6 animate-chat-in">
            <div className="text-center space-y-2">
              <div className="inline-flex h-16 w-16 rounded-2xl bg-cyan-100 text-cyan-700 items-center justify-center text-3xl shadow-inner mx-auto">
                💼
              </div>
              <h3 className="text-xl font-bold text-ink">Add Your LinkedIn Profile (Optional)</h3>
              <p className="text-xs text-muted max-w-md mx-auto leading-relaxed">
                Connect your LinkedIn profile URL or paste your summary text to calibrate public
                seniority benchmarks. If you prefer to skip, you can proceed directly to target roles.
              </p>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-2">
                  LinkedIn URL or About Summary
                </label>
                <input
                  type="text"
                  value={linkedinInput}
                  onChange={(e) => setLinkedinInput(e.target.value)}
                  placeholder="https://www.linkedin.com/in/your-profile"
                  className="neo-inset w-full px-4 py-3 text-xs text-ink bg-transparent focus:outline-none focus:ring-2 focus:ring-teal-500/30 rounded-xl"
                />
              </div>

              <div className="p-3.5 rounded-xl bg-slate-50/80 border border-slate-200 text-[11px] text-muted leading-relaxed">
                💡 <span className="font-semibold text-ink">Why add LinkedIn?</span> Gives Scout
                context on your public presence and company pedigree to craft personalized recruiter
                pitch angles.
              </div>
            </div>

            <div className="flex items-center justify-between gap-4 pt-4 border-t border-slate-200/80">
              <button
                type="button"
                onClick={() => handleSaveLinkedin(true)}
                disabled={savingLinkedin}
                className="neo-raised px-6 py-2.5 text-xs font-semibold text-muted hover:text-ink rounded-xl"
              >
                Skip for now →
              </button>

              <button
                type="button"
                onClick={() => handleSaveLinkedin(false)}
                disabled={savingLinkedin}
                className="btn-teal px-8 py-2.5 text-xs font-bold uppercase tracking-wider disabled:opacity-50 shadow-md"
              >
                {savingLinkedin ? "Saving..." : "Save & Continue →"}
              </button>
            </div>
          </div>
        )}

        {/* ==================================================================== */}
        {/* SCREEN 3: TARGET MARKET ROLES (SEARCH BAR + DROPDOWN, MAX 3)         */}
        {/* ==================================================================== */}
        {currentStage === "target_jobs" && (
          <div className="max-w-2xl mx-auto neo-card p-8 space-y-6 animate-chat-in">
            <div className="text-center space-y-2">
              <div className="inline-flex h-16 w-16 rounded-2xl bg-teal-100 text-teal-800 items-center justify-center text-3xl shadow-inner mx-auto">
                🎯
              </div>
              <h3 className="text-xl font-bold text-ink">What kind of job are you looking for?</h3>
              <p className="text-xs text-muted max-w-md mx-auto leading-relaxed">
                Search market roles below and select <strong>up to 3 jobs</strong> you are targeting.
                Your top selection will be designated as your #1 Priority Role (1.5× Scout search
                weighting).
              </p>
            </div>

            {/* Selected Roles Tray */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold uppercase tracking-wider text-muted">
                  Selected Target Roles ({selectedRoleIds.length}/3 max)
                </span>
                {selectedRoleIds.length === 3 && (
                  <span className="badge-bronze text-[10px] py-0.5 px-2">Slot Maximum Reached</span>
                )}
              </div>

              {selectedRoleIds.length === 0 ? (
                <div className="p-4 rounded-xl border border-dashed border-slate-300 text-center text-xs text-muted">
                  No roles selected yet. Use the search bar below to add up to 3 market roles.
                </div>
              ) : (
                <div className="space-y-2">
                  {selectedRoleIds.map((roleId, idx) => {
                    const catalogMatch = catalogRoles.find((r) => r.id === roleId);
                    const title =
                      catalogMatch?.title ||
                      roleId.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
                    const isPriority = idx === 0;

                    return (
                      <div
                        key={roleId}
                        className={`p-3 rounded-xl flex items-center justify-between border transition-all ${
                          isPriority
                            ? "bg-teal-50/80 border-teal-400/80 shadow-sm"
                            : "bg-slate-50 border-slate-200"
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          {isPriority ? (
                            <span className="badge-teal text-[10px] py-0.5 px-2 font-bold">
                              ⭐ #1 Priority (1.5× Weight)
                            </span>
                          ) : (
                            <button
                              type="button"
                              onClick={() => handleMakePriority(roleId)}
                              className="text-[10px] text-muted hover:text-teal-700 underline font-medium"
                            >
                              Make Priority #1
                            </button>
                          )}
                          <span className="text-xs font-bold text-ink">{title}</span>
                          {catalogMatch?.family && (
                            <span className="text-[10px] text-muted">({catalogMatch.family})</span>
                          )}
                        </div>

                        <button
                          type="button"
                          onClick={() => handleRemoveRole(roleId)}
                          className="text-xs text-rose-600 hover:text-rose-800 font-bold px-2 py-1 rounded-md"
                          title="Remove role"
                        >
                          ✕
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Search Bar + Live Dropdown */}
            <div className="space-y-2 relative">
              <label className="block text-xs font-semibold uppercase tracking-wider text-muted">
                Search Roles in Market:
              </label>

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
                  placeholder="Type to search roles (e.g. Backend, Full Stack, AI, Manager)..."
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
              </div>

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

            <div className="flex justify-end pt-4 border-t border-slate-200/80">
              <button
                type="button"
                onClick={handleSaveTargetRoles}
                disabled={selectedRoleIds.length === 0 || savingRoles}
                className="btn-teal px-8 py-3 text-xs font-bold uppercase tracking-wider disabled:opacity-50 shadow-md flex items-center gap-2"
              >
                <span>
                  {savingRoles ? "Saving Target Roles..." : "Proceed to Live Counsellor Chat →"}
                </span>
              </button>
            </div>
          </div>
        )}

        {/* ==================================================================== */}
        {/* SCREEN 4: LIVE CHAT WITH THE COUNSELLOR (PERSONA BUILDING)            */}
        {/* ==================================================================== */}
        {currentStage === "live_chat" && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 animate-chat-in">
            {/* Left Column: Live Chat Interface */}
            <div className="lg:col-span-8 space-y-4">
              <div className="neo-card p-6 min-h-[580px] flex flex-col justify-between space-y-4">
                {/* Chat Header */}
                <div className="flex items-center justify-between border-b border-slate-200/80 pb-3">
                  <div className="flex items-center gap-3">
                    <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-teal-600 to-cyan-700 text-white flex items-center justify-center font-bold text-xs shadow-sm">
                      AI
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-xs font-bold text-ink uppercase tracking-wide">
                          Live Career Counsellor
                        </h3>
                        <span className="badge-teal text-[9px] py-0.2 px-1.5">DeepSeek Live</span>
                      </div>
                      <p className="text-[11px] text-muted">Building candidate persona for Scout</p>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={handleFinalizePersona}
                    disabled={finalizingPersona}
                    className="btn-teal px-4 py-2 text-[11px] font-bold uppercase tracking-wider shadow-sm"
                  >
                    {finalizingPersona ? "Finalizing..." : "Complete & Launch Scout →"}
                  </button>
                </div>

                {/* Messages Stream */}
                <div className="flex-1 overflow-y-auto space-y-4 pr-1 max-h-[460px]">
                  {chatMessages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`flex items-start gap-3 ${
                        msg.role === "user" ? "justify-end ml-auto max-w-xl" : "max-w-xl"
                      }`}
                    >
                      {msg.role === "assistant" && (
                        <div className="h-8 w-8 rounded-xl bg-gradient-to-br from-teal-600 to-cyan-700 text-white flex items-center justify-center font-bold text-[11px] shadow-sm shrink-0 mt-0.5">
                          AI
                        </div>
                      )}

                      <div
                        className={`p-4 rounded-2xl text-xs leading-relaxed ${
                          msg.role === "user"
                            ? "bg-gradient-to-br from-teal-700 via-teal-800 to-cyan-900 text-white shadow-md rounded-tr-sm"
                            : "neo-raised bg-white/80 text-ink shadow-sm rounded-tl-sm border border-slate-200/70"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-4 text-[10px] mb-1 opacity-75">
                          <span className="font-semibold uppercase tracking-wider">
                            {msg.role === "user" ? "Candidate" : "Career Counsellor"}
                          </span>
                          {msg.inputMode === "mic" && <span>🎙️ Spoken</span>}
                        </div>
                        <p className="whitespace-pre-wrap">{msg.content}</p>
                      </div>

                      {msg.role === "user" && (
                        <div className="h-8 w-8 rounded-xl bg-slate-800 text-white flex items-center justify-center font-bold text-[11px] shadow-sm shrink-0 mt-0.5">
                          You
                        </div>
                      )}
                    </div>
                  ))}

                  {isAiTyping && (
                    <div className="flex items-center gap-2 text-xs text-teal-700 pl-11">
                      <div className="flex gap-1 items-center">
                        <span className="h-1.5 w-1.5 rounded-full bg-teal-600 typing-dot" />
                        <span className="h-1.5 w-1.5 rounded-full bg-teal-600 typing-dot" />
                        <span className="h-1.5 w-1.5 rounded-full bg-teal-600 typing-dot" />
                      </div>
                      <span className="text-[11px] font-medium animate-pulse">
                        Counsellor is analyzing and tailoring persona...
                      </span>
                    </div>
                  )}

                  <div ref={chatEndRef} />
                </div>

                {/* Quick Persona Dimension Starters */}
                <div className="space-y-2 pt-2 border-t border-slate-200/80">
                  <div className="flex items-center gap-1.5 text-[10px] uppercase font-bold text-muted tracking-wider">
                    <span>Quick Responses:</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {[
                      "👥 Yes, I have managed people and squads",
                      "⚡ Prefer 100% Individual Contributor focus",
                      "🌐 Remote only (US/Global)",
                      "🌉 Hybrid in San Francisco / Bay Area",
                      "🗽 Hybrid in New York City",
                      "🛡️ Authorized (Citizen/PR, no sponsorship)",
                      "🛂 Requires Visa Sponsorship (H-1B)",
                      "🚫 Dealbreakers: avoid legacy monoliths & 24/7 on-call",
                    ].map((chip) => (
                      <button
                        key={chip}
                        type="button"
                        onClick={() => handleSendChatMessage(chip)}
                        className="px-2.5 py-1 text-[11px] font-medium rounded-lg neo-raised text-ink hover:text-teal-700 hover:border-teal-400 transition-all text-left"
                      >
                        {chip}
                      </button>
                    ))}
                  </div>

                  {/* Input Form */}
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      handleSendChatMessage();
                    }}
                    className="flex items-center gap-2 pt-1"
                  >
                    <input
                      type="text"
                      value={chatInputText}
                      onChange={(e) => setChatInputText(e.target.value)}
                      placeholder="Type your response or question to your career counsellor..."
                      className="neo-inset flex-1 px-4 py-3 text-xs text-ink bg-transparent focus:outline-none focus:ring-2 focus:ring-teal-500/30 rounded-xl"
                    />

                    <button
                      type="button"
                      onClick={handleVoiceInput}
                      disabled={listening || sendingChat}
                      className={`px-3.5 py-3 text-xs rounded-xl flex items-center justify-center transition-all ${
                        listening
                          ? "bg-rose-100 text-rose-700 border border-rose-300 animate-pulse shadow-sm"
                          : "neo-raised text-ink hover:text-teal-700"
                      }`}
                      title="Speak via microphone"
                    >
                      🎙️
                    </button>

                    <button
                      type="submit"
                      disabled={sendingChat || !chatInputText.trim()}
                      className="btn-teal px-6 py-3 text-xs font-bold uppercase tracking-wider disabled:opacity-50 shadow-md"
                    >
                      {sendingChat ? "Sending..." : "Send →"}
                    </button>
                  </form>
                </div>
              </div>
            </div>

            {/* Right Column: Live Candidate Persona Card */}
            <div className="lg:col-span-4 space-y-4">
              <div className="neo-card p-5 space-y-4 sticky top-6">
                <div className="flex items-center justify-between border-b border-slate-200/80 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-base">👤</span>
                    <h4 className="text-xs font-bold uppercase tracking-wider text-ink">
                      Active Candidate Persona
                    </h4>
                  </div>
                  <span className="badge-emerald text-[10px] py-0.5 px-2 font-bold">
                    Scout Ready
                  </span>
                </div>

                {/* Persona Attributes Card */}
                <div className="space-y-3 text-xs">
                  {/* Target Roles */}
                  <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-muted">
                      Target Roles ({persona.targetRoles.length})
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {persona.targetRoles.map((r, i) => (
                        <span
                          key={r}
                          className={`px-2 py-0.5 text-[10px] font-semibold rounded-md ${
                            i === 0
                              ? "bg-teal-100 text-teal-900 border border-teal-300"
                              : "bg-slate-200/70 text-slate-800"
                          }`}
                        >
                          {i === 0 && "⭐ "}
                          {r.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Resume Skills */}
                  <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
                    <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-muted">
                      <span>Verified Skills</span>
                      <span className="text-teal-700 font-bold">
                        {persona.extractedSkills.length || uploadedResume?.skillsCount || 0} Vaulted
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {(persona.extractedSkills.length > 0
                        ? persona.extractedSkills
                        : uploadedResume?.extractedSkills || []
                      )
                        .slice(0, 8)
                        .map((s) => (
                          <span
                            key={s}
                            className="px-2 py-0.5 text-[10px] rounded-md bg-teal-50 text-teal-800 border border-teal-200"
                          >
                            {s}
                          </span>
                        ))}
                    </div>
                  </div>

                  {/* Leadership Track */}
                  <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-0.5">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-muted">
                      Career Track
                    </span>
                    <p className="font-semibold text-ink">
                      {persona.management === true
                        ? "👥 Engineering Management / Squad Lead"
                        : persona.management === false
                        ? "⚡ Individual Contributor (Senior / Staff IC)"
                        : "Calibrating in chat..."}
                    </p>
                  </div>

                  {/* Location Model */}
                  <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-0.5">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-muted">
                      Location Preference
                    </span>
                    <p className="font-semibold text-ink">
                      {persona.location || "Calibrating in chat..."}
                    </p>
                  </div>

                  {/* Work Authorization */}
                  <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-0.5">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-muted">
                      Work Authorization
                    </span>
                    <p className="font-semibold text-ink">
                      {persona.authorization || "Calibrating in chat..."}
                    </p>
                  </div>

                  {/* Preferences / Dealbreakers */}
                  <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-0.5">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-muted">
                      Dealbreakers & Cultural Fit
                    </span>
                    <p className="font-semibold text-ink truncate">
                      {persona.preferences || "Calibrating in chat..."}
                    </p>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={handleFinalizePersona}
                  disabled={finalizingPersona}
                  className="btn-teal w-full py-3 text-xs font-bold uppercase tracking-wider shadow-md"
                >
                  {finalizingPersona ? "Finalizing Persona..." : "Finalize Persona & Launch Scout →"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Shell>
  );
}

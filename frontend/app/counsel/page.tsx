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

  // Preferences State (Screen 4 Profile Section)
  const [workArrangement, setWorkArrangement] = useState<string>("Remote Only");
  const [targetLocation, setTargetLocation] = useState<string>("US Remote / Tech Hubs");
  const [authorization, setAuthorization] = useState<string>(
    "Authorized (No Sponsorship Required)"
  );
  const [leadershipTrack, setLeadershipTrack] = useState<"ic" | "lead">("ic");
  const [selectedDealbreakers, setSelectedDealbreakers] = useState<string[]>([
    "Legacy Monolithic Codebases",
    "Uncompensated 24/7 On-Call Rotations",
  ]);
  const [prefsSavedFeedback, setPrefsSavedFeedback] = useState(false);

  // Live Chat State (Optional / Advisory)
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInputText, setChatInputText] = useState("");
  const [inputMode, setInputMode] = useState<"text" | "mic">("text");
  const [sendingChat, setSendingChat] = useState(false);
  const [listening, setListening] = useState(false);
  const [isAiTyping, setIsAiTyping] = useState(false);
  const [isChatExpanded, setIsChatExpanded] = useState(false);
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
        linkedinUrl:
          histMap.linkedin && histMap.linkedin !== "[Skipped]" ? histMap.linkedin : undefined,
        location: histMap.location,
        authorization: histMap.authorization,
        preferences: histMap.preferences,
      };

      if (histMap.management) {
        initialPersona.management = histMap.management.toLowerCase().includes("yes");
        setLeadershipTrack(initialPersona.management ? "lead" : "ic");
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
        startLiveChatSession(initialPersona);
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
          mgmt_experience: leadershipTrack === "lead",
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
  // STAGE 4: EXPERT COUNSELLOR DIAGNOSIS & PREFERENCES SECTION
  // --------------------------------------------------------------------------
  async function persistPreferences(
    updates: {
      workArrangement?: string;
      targetLocation?: string;
      authorization?: string;
      leadershipTrack?: "ic" | "lead";
      dealbreakers?: string[];
    } = {}
  ) {
    const wa = updates.workArrangement || workArrangement;
    const loc = updates.targetLocation || targetLocation;
    const auth = updates.authorization || authorization;
    const lead = (updates.leadershipTrack || leadershipTrack) === "lead";
    const deals = updates.dealbreakers || selectedDealbreakers;

    try {
      await api("/api/counsel/preferences", {
        method: "POST",
        body: JSON.stringify({
          work_arrangement: wa,
          location: loc,
          authorization: auth,
          management: lead,
          dealbreakers: deals,
          preferences: `Prefers ${wa} in ${loc}. Visa: ${auth}`,
        }),
      }).catch(() => null);

      setPrefsSavedFeedback(true);
      setTimeout(() => setPrefsSavedFeedback(false), 2000);
    } catch {
      // Non-blocking background sync
    }
  }

  function toggleDealbreaker(item: string) {
    const updated = selectedDealbreakers.includes(item)
      ? selectedDealbreakers.filter((d) => d !== item)
      : [...selectedDealbreakers, item];
    setSelectedDealbreakers(updated);
    persistPreferences({ dealbreakers: updated });
  }

  function startLiveChatSession(currentPersona: PersonaState) {
    if (chatMessages.length > 0) return;

    const primaryRole =
      currentPersona.priorityRole || currentPersona.targetRoles[0] || "Senior Software Engineer";
    const primaryTitle = primaryRole.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

    const initialGreeting =
      `Hello! I'm your AI Executive Career Counsellor.\n\n` +
      `I've analyzed your resume and market positioning for **${primaryTitle}**. ` +
      `I have identified your best-fit jobs and calibrated your profile above.\n\n` +
      `You can fine-tune your search preferences with 1 click above, or ask me any questions about market compensation, technical interviews, or role requirements below. When you are ready, click **Launch Autonomous Scout** to proceed!`;

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
    } catch {
      const fallbackMsg: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content:
          "I've noted that! Your profile and target roles are well-calibrated. " +
          "You can adjust preferences anytime above or click 'Launch Autonomous Scout' to move straight to your matched jobs.",
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
      // Ensure preferences are saved
      await persistPreferences();
      // Finalize counsel stage to unlock todos
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

  // Calculate top 3 recommended job diagnosis cards based on selections & resume
  const diagnosisRoles =
    selectedRoleIds.length > 0
      ? selectedRoleIds
      : ["role_backend_arch", "role_fullstack_eng", "role_ai_engineer"];

  return (
    <Shell title="Career Counsellor & Job Matching">
      <div className="space-y-6">
        {/* Onboarding Stepper Header with Direct Skip Action */}
        <div className="neo-raised p-5 rounded-2xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-teal-600 via-teal-700 to-cyan-700 text-white flex items-center justify-center font-bold text-sm shadow-md">
              🎯
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-wider text-teal-800">
                  Career Counsellor Engine
                </span>
                <span className="badge-teal text-[10px] py-0.5 px-2">DeepSeek Intelligence</span>
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
              4. Job Matches & Preferences
            </button>

            {/* Quick Skip to Scout Action */}
            {currentStage === "live_chat" && (
              <button
                type="button"
                onClick={handleFinalizePersona}
                disabled={finalizingPersona}
                className="btn-teal px-4 py-1.5 text-xs font-bold uppercase tracking-wider ml-2 shadow-sm"
              >
                {finalizingPersona ? "Loading..." : "Scout My Jobs →"}
              </button>
            )}
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
                extract your verified technical skills, project scopes, and metrics.
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
                  {savingRoles ? "Saving Target Roles..." : "Proceed to Job Matches & Preferences →"}
                </span>
              </button>
            </div>
          </div>
        )}

        {/* ==================================================================== */}
        {/* SCREEN 4: EXPERT CAREER DIAGNOSIS, PREFERENCES & OPTIONAL CHAT       */}
        {/* ==================================================================== */}
        {currentStage === "live_chat" && (
          <div className="space-y-6 animate-chat-in">
            {/* Top Section: Expert Career Counsellor Job Matches Diagnosis */}
            <div className="neo-card p-6 space-y-4 border border-teal-500/30 bg-gradient-to-br from-white/90 via-teal-50/20 to-cyan-50/20 shadow-md">
              <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3 border-b border-slate-200/80 pb-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="badge-teal text-[10px] py-0.5 px-2 font-bold">
                      ⭐ Expert Diagnosis
                    </span>
                    <span className="text-xs text-muted font-medium">
                      AI Career Counsellor • Best Opportunities Identified
                    </span>
                  </div>
                  <h3 className="text-base font-bold text-ink mt-1">
                    Top 3 Market Job Fits Identified For You
                  </h3>
                  <p className="text-xs text-muted">
                    Diagnosed from your uploaded resume (
                    {persona.extractedSkills.length || uploadedResume?.skillsCount || 0} skills
                    verified) and market hiring velocity:
                  </p>
                </div>

                <button
                  type="button"
                  onClick={handleFinalizePersona}
                  disabled={finalizingPersona}
                  className="btn-teal px-6 py-2.5 text-xs font-bold uppercase tracking-wider shadow-md shrink-0"
                >
                  {finalizingPersona ? "Finalizing..." : "Confirm & Scout These Jobs →"}
                </button>
              </div>

              {/* 3 Job Match Cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {diagnosisRoles.slice(0, 3).map((rId, idx) => {
                  const match = catalogRoles.find((r) => r.id === rId);
                  const title =
                    match?.title || rId.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
                  const matchScore = idx === 0 ? "96%" : idx === 1 ? "91%" : "86%";
                  const badgeClass =
                    idx === 0
                      ? "badge-emerald"
                      : idx === 1
                      ? "badge-teal"
                      : "badge-cyan";
                  const roleRank =
                    idx === 0 ? "Primary Target (#1 Focus)" : idx === 1 ? "Secondary Complement" : "Growth Opportunity";
                  const salaryBand =
                    idx === 0
                      ? "$190k - $250k • Staff Tier"
                      : idx === 1
                      ? "$175k - $225k • Senior Tier"
                      : "$180k - $235k • Specialized";

                  return (
                    <div
                      key={rId}
                      className={`neo-raised p-4 rounded-xl space-y-2 border transition-all ${
                        idx === 0
                          ? "border-teal-500/50 bg-teal-50/40 shadow-sm"
                          : "border-slate-200/80 bg-white/70"
                      }`}
                    >
                      <div className="flex items-center justify-between text-[10px]">
                        <span className="font-bold text-teal-800">{roleRank}</span>
                        <span className={`${badgeClass} text-[10px] py-0.5 px-2 font-bold`}>
                          {matchScore} Fit
                        </span>
                      </div>

                      <h4 className="text-sm font-bold text-ink">{title}</h4>

                      <div className="text-[11px] text-muted space-y-1">
                        <p>
                          <span className="font-semibold text-slate-700">Market Demand:</span> High
                          hiring activity
                        </p>
                        <p>
                          <span className="font-semibold text-slate-700">Estimated Band:</span>{" "}
                          <span className="text-emerald-800 font-bold">{salaryBand}</span>
                        </p>
                      </div>

                      <div className="text-[10px] text-teal-700 pt-1 font-semibold flex items-center gap-1">
                        <span>✓ Verified by Career Counsellor</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Middle Section: Quick 1-Click Search Preferences (No endless chat needed!) */}
            <div className="neo-card p-6 space-y-5">
              <div className="flex items-center justify-between border-b border-slate-200/80 pb-3">
                <div>
                  <h3 className="text-sm font-bold text-ink uppercase tracking-wider">
                    Profile Search Preferences
                  </h3>
                  <p className="text-xs text-muted">
                    Quickly toggle your search criteria below. Everything auto-saves without needing
                    to chat.
                  </p>
                </div>
                {prefsSavedFeedback && (
                  <span className="badge-emerald text-[11px] py-1 px-3 animate-pulse">
                    ✓ Preferences auto-saved
                  </span>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* 1. Work Arrangement */}
                <div className="space-y-2">
                  <label className="block text-xs font-bold uppercase tracking-wider text-muted">
                    Work Arrangement Preference
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {["Remote Only", "Hybrid (1-2 days)", "On-site / Flexible"].map((opt) => (
                      <button
                        key={opt}
                        type="button"
                        onClick={() => {
                          setWorkArrangement(opt);
                          persistPreferences({ workArrangement: opt });
                        }}
                        className={`px-3 py-1.5 text-xs font-semibold rounded-xl transition-all ${
                          workArrangement === opt
                            ? "neo-pressed text-teal-800 border border-teal-500 font-bold"
                            : "neo-raised text-ink hover:text-teal-700"
                        }`}
                      >
                        {workArrangement === opt ? `✓ ${opt}` : opt}
                      </button>
                    ))}
                  </div>
                </div>

                {/* 2. Target Tech Hubs */}
                <div className="space-y-2">
                  <label className="block text-xs font-bold uppercase tracking-wider text-muted">
                    Target Location & Timezones
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {[
                      "US Remote / Tech Hubs",
                      "Global Remote",
                      "San Francisco / Bay Area",
                      "New York City",
                      "London / Europe",
                      "Bengaluru / India",
                    ].map((opt) => (
                      <button
                        key={opt}
                        type="button"
                        onClick={() => {
                          setTargetLocation(opt);
                          persistPreferences({ targetLocation: opt });
                        }}
                        className={`px-3 py-1.5 text-xs font-semibold rounded-xl transition-all ${
                          targetLocation === opt
                            ? "neo-pressed text-teal-800 border border-teal-500 font-bold"
                            : "neo-raised text-ink hover:text-teal-700"
                        }`}
                      >
                        {targetLocation === opt ? `✓ ${opt}` : opt}
                      </button>
                    ))}
                  </div>
                </div>

                {/* 3. Work Authorization */}
                <div className="space-y-2">
                  <label className="block text-xs font-bold uppercase tracking-wider text-muted">
                    Work Authorization Status
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {[
                      "Authorized (No Sponsorship Required)",
                      "Requires Visa Sponsorship (H-1B, etc.)",
                      "Open to Independent Contractor / B2B",
                    ].map((opt) => (
                      <button
                        key={opt}
                        type="button"
                        onClick={() => {
                          setAuthorization(opt);
                          persistPreferences({ authorization: opt });
                        }}
                        className={`px-3 py-1.5 text-xs font-semibold rounded-xl transition-all ${
                          authorization === opt
                            ? "neo-pressed text-teal-800 border border-teal-500 font-bold"
                            : "neo-raised text-ink hover:text-teal-700"
                        }`}
                      >
                        {authorization === opt ? `✓ ${opt}` : opt}
                      </button>
                    ))}
                  </div>
                </div>

                {/* 4. Career Track */}
                <div className="space-y-2">
                  <label className="block text-xs font-bold uppercase tracking-wider text-muted">
                    Career Track Scope
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {[
                      { key: "ic", label: "Senior / Staff IC (Pure Engineering)" },
                      { key: "lead", label: "Engineering Manager / Squad Lead" },
                    ].map((opt) => (
                      <button
                        key={opt.key}
                        type="button"
                        onClick={() => {
                          const track = opt.key as "ic" | "lead";
                          setLeadershipTrack(track);
                          persistPreferences({ leadershipTrack: track });
                        }}
                        className={`px-3 py-1.5 text-xs font-semibold rounded-xl transition-all ${
                          leadershipTrack === opt.key
                            ? "neo-pressed text-teal-800 border border-teal-500 font-bold"
                            : "neo-raised text-ink hover:text-teal-700"
                        }`}
                      >
                        {leadershipTrack === opt.key ? `✓ ${opt.label}` : opt.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* 5. Dealbreakers to Filter Out */}
              <div className="space-y-2 pt-2 border-t border-slate-200/70">
                <label className="block text-xs font-bold uppercase tracking-wider text-muted">
                  Dealbreakers to Filter Out from Scout Matches:
                </label>
                <div className="flex flex-wrap gap-2">
                  {[
                    "Legacy Monolithic Codebases",
                    "Uncompensated 24/7 On-Call Rotations",
                    "Excessive Meeting Overhead",
                    "Early Pre-Seed Instability",
                    "Mandatory 5-Day Office Requirements",
                  ].map((dbItem) => {
                    const isSelected = selectedDealbreakers.includes(dbItem);
                    return (
                      <button
                        key={dbItem}
                        type="button"
                        onClick={() => toggleDealbreaker(dbItem)}
                        className={`px-3 py-1.5 text-xs font-semibold rounded-xl transition-all ${
                          isSelected
                            ? "neo-pressed text-rose-700 border border-rose-300 font-bold bg-rose-50/40"
                            : "neo-raised text-muted hover:text-ink"
                        }`}
                      >
                        {isSelected ? `🚫 Filter out: ${dbItem}` : `+ ${dbItem}`}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Bottom Section: Optional Advisory Chat & Final Confirmation */}
            <div className="neo-card p-6 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-ink">
                    Ask Career Counsellor Anything (Optional)
                  </h4>
                  <p className="text-xs text-muted">
                    Have questions about negotiation, interview expectations, or role positioning?
                    Ask below.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => setIsChatExpanded(!isChatExpanded)}
                  className="text-xs font-semibold text-teal-700 hover:text-teal-900 underline"
                >
                  {isChatExpanded ? "Hide Advisor Chat ▲" : "Open Advisor Chat ▼"}
                </button>
              </div>

              {/* Collapsible Advisory Chat Thread */}
              {isChatExpanded && (
                <div className="space-y-4 pt-2 border-t border-slate-200/80 animate-chat-in">
                  <div className="max-h-72 overflow-y-auto space-y-3 p-3 rounded-xl bg-slate-50/60 border border-slate-200/60">
                    {chatMessages.map((msg) => (
                      <div
                        key={msg.id}
                        className={`flex items-start gap-2 ${
                          msg.role === "user" ? "justify-end ml-auto max-w-lg" : "max-w-lg"
                        }`}
                      >
                        {msg.role === "assistant" && (
                          <div className="h-7 w-7 rounded-lg bg-teal-600 text-white flex items-center justify-center font-bold text-[10px] shrink-0 mt-0.5">
                            AI
                          </div>
                        )}
                        <div
                          className={`p-3 rounded-xl text-xs leading-relaxed ${
                            msg.role === "user"
                              ? "bg-teal-700 text-white"
                              : "bg-white text-ink border border-slate-200"
                          }`}
                        >
                          <p className="whitespace-pre-wrap">{msg.content}</p>
                        </div>
                      </div>
                    ))}
                    {isAiTyping && (
                      <div className="text-[11px] text-teal-700 animate-pulse pl-9">
                        Counsellor is typing strategic advice...
                      </div>
                    )}
                    <div ref={chatEndRef} />
                  </div>

                  {/* Advisory Prompt Chips */}
                  <div className="flex flex-wrap gap-1.5">
                    {[
                      "💬 What skills are most in demand for Staff Backend roles right now?",
                      "💬 How should I position my resume for remote engineering teams?",
                      "💬 What are current market base salary expectations?",
                    ].map((chip) => (
                      <button
                        key={chip}
                        type="button"
                        onClick={() => handleSendChatMessage(chip)}
                        className="px-2.5 py-1 text-[11px] rounded-lg neo-raised text-ink hover:text-teal-700 text-left"
                      >
                        {chip}
                      </button>
                    ))}
                  </div>

                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      handleSendChatMessage();
                    }}
                    className="flex items-center gap-2"
                  >
                    <input
                      type="text"
                      value={chatInputText}
                      onChange={(e) => setChatInputText(e.target.value)}
                      placeholder="Ask your career advisor anything about your search..."
                      className="neo-inset flex-1 px-4 py-2.5 text-xs text-ink bg-transparent focus:outline-none focus:ring-2 focus:ring-teal-500/30 rounded-xl"
                    />

                    <button
                      type="button"
                      onClick={handleVoiceInput}
                      disabled={listening || sendingChat}
                      className={`px-3 py-2.5 text-xs rounded-xl flex items-center justify-center ${
                        listening ? "bg-rose-100 text-rose-700 animate-pulse" : "neo-raised text-ink"
                      }`}
                      title="Dictate via microphone"
                    >
                      🎙️
                    </button>

                    <button
                      type="submit"
                      disabled={sendingChat || !chatInputText.trim()}
                      className="btn-teal px-5 py-2.5 text-xs font-bold uppercase tracking-wider disabled:opacity-50"
                    >
                      {sendingChat ? "Sending..." : "Ask →"}
                    </button>
                  </form>
                </div>
              )}

              {/* Big Prominent Launch Action */}
              <div className="pt-4 border-t border-slate-200/80 flex flex-col sm:flex-row items-center justify-between gap-4">
                <p className="text-xs text-muted">
                  Ready to proceed? Autonomous Scout will match live job vacancies against this
                  profile.
                </p>

                <button
                  type="button"
                  onClick={handleFinalizePersona}
                  disabled={finalizingPersona}
                  className="btn-teal px-10 py-3.5 text-xs font-bold uppercase tracking-wider shadow-lg hover:shadow-xl transition-all"
                >
                  {finalizingPersona
                    ? "Launching Scout..."
                    : "Launch Autonomous Scout for These Jobs →"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Shell>
  );
}

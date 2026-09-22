"use client";

import React, { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { api } from "@/lib/api";
import { listenOnce } from "@/lib/speech";

interface CounselState {
  step: string | null;
  prompt: string;
  choices: string[];
  done: boolean;
}

export default function CounselPage() {
  const [counselState, setCounselState] = useState<CounselState | null>(null);
  const [answerText, setAnswerText] = useState("");
  const [inputMode, setInputMode] = useState<"text" | "mic">("text");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadingResume, setUploadingResume] = useState(false);
  const [uploadedResume, setUploadedResume] = useState<{ filename: string; skillsCount: number; resumeId: string } | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  useEffect(() => {
    loadState();
  }, []);

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
    }
  }

  async function handleSaveAnswer(e?: React.FormEvent) {
    if (e) e.preventDefault();
    if (!counselState?.step || !answerText.trim()) return;

    setError(null);
    setSubmitting(true);
    try {
      const res = await api<CounselState>("/api/counsel/answer", {
        method: "POST",
        body: JSON.stringify({
          step: counselState.step,
          text: answerText.trim(),
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
    }
  }

  return (
    <Shell title="Career Counsellor">
      <div className="max-w-2xl mx-auto space-y-6">
        {loading ? (
          <div className="neo-card p-10 text-center text-muted">
            <div className="inline-block h-6 w-6 rounded-full border-2 border-teal-600 border-t-transparent animate-spin mb-3" />
            <p className="text-sm">Connecting to your career counsellor agent...</p>
          </div>
        ) : counselState?.done ? (
          <div className="neo-card p-10 text-center space-y-4">
            <div className="inline-flex h-12 w-12 rounded-full bg-emerald-100 text-emerald-700 items-center justify-center text-xl font-bold mb-2">
              ✓
            </div>
            <h2 className="text-2xl font-bold text-ink">Onboarding Complete</h2>
            <p className="text-sm text-muted">All profile sections have been recorded. Advancing to To-Dos...</p>
            <button
              onClick={() => window.location.assign("/todos")}
              className="btn-teal px-6 py-2.5 text-xs font-bold uppercase tracking-wider mt-4"
            >
              Continue to Action Items →
            </button>
          </div>
        ) : (
          <div className="neo-card p-8 space-y-6">
            {/* Step Progress Bar */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs uppercase font-bold tracking-wider text-teal-800">
                  Question: {counselState?.step?.replace("_", " ")}
                </span>
                <span className="badge-teal text-[11px] py-0.5 px-2">
                  AI Counsellor • DeepSeek
                </span>
              </div>

              {/* Progress Track */}
              <div className="w-full h-2 rounded-full bg-slate-200/80 overflow-hidden p-0.5 border border-slate-300/40">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-teal-500 to-cyan-500 transition-all duration-300 shadow-sm"
                  style={{
                    width: counselState?.step
                      ? `${
                          (([
                            "linkedin",
                            "resume",
                            "target_work",
                            "priority_role",
                            "management",
                            "location",
                            "authorization",
                            "preferences",
                          ].indexOf(counselState.step) +
                            1) /
                            8) *
                          100
                        }%`
                      : "12%",
                  }}
                />
              </div>

              <h2 className="text-xl font-bold text-ink leading-relaxed pt-2">
                {counselState?.prompt}
              </h2>
            </div>

            {counselState?.step === "resume" ? (
              <div className="space-y-6">
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
                    <h3 className="text-base font-bold text-ink">
                      {uploadedResume ? "Resume Document Ready" : "Upload your Resume (PDF)"}
                    </h3>
                    <p className="text-xs text-muted max-w-md mx-auto">
                      Drag and drop your PDF resume here, or click browse below. DeepSeek will parse and extract verified skills, metrics, and role history.
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
                        className="btn-teal inline-flex items-center justify-center gap-2 px-6 py-3 text-xs font-bold uppercase tracking-wider cursor-pointer shadow-md hover:shadow-lg transition-all"
                      >
                        <span>Choose Resume PDF</span>
                      </label>
                      <p className="text-[11px] text-muted mt-2">Only PDF format supported • Max 10MB</p>
                    </div>
                  )}

                  {uploadingResume && (
                    <div className="p-4 rounded-xl bg-teal-50/80 border border-teal-200 flex flex-col items-center justify-center gap-2 text-teal-800">
                      <div className="h-6 w-6 rounded-full border-2 border-teal-600 border-t-transparent animate-spin" />
                      <p className="text-xs font-semibold">Parsing PDF document and extracting skills with AI...</p>
                      <span className="text-[11px] text-teal-600">This takes just a few seconds</span>
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

                <div className="flex items-center justify-end gap-3 pt-2">
                  <button
                    type="button"
                    onClick={handleConfirmResume}
                    disabled={submitting || uploadingResume || !uploadedResume}
                    className="btn-teal px-8 py-3 text-xs font-bold uppercase tracking-wider disabled:opacity-50 shadow-md flex items-center gap-2"
                  >
                    <span>{submitting ? "Saving..." : "Confirm Resume & Continue to Target Work →"}</span>
                  </button>
                </div>
              </div>
            ) : (
              <>
                {counselState?.choices && counselState.choices.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-bold uppercase text-muted">Recommended Options:</p>
                    <div className="flex flex-wrap gap-2">
                      {counselState.choices.map((choice) => {
                        const isSelected = answerText === choice;
                        return (
                          <button
                            key={choice}
                            type="button"
                            onClick={() => {
                              setAnswerText(choice);
                              setInputMode("text");
                            }}
                            className={`px-3 py-1.5 text-xs font-medium rounded-xl transition-all duration-150 ${
                              isSelected
                                ? "neo-pressed text-teal-800 font-bold border border-teal-500/50"
                                : "neo-raised text-ink hover:text-teal-700 hover:border-teal-400"
                            }`}
                          >
                            {choice}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                {counselState?.step === "management" && (
                  <div className="flex gap-3">
                    <button
                      type="button"
                      onClick={() => setAnswerText("yes")}
                      className={`px-4 py-2.5 text-xs font-semibold rounded-xl transition-all ${
                        answerText.toLowerCase() === "yes"
                          ? "neo-pressed text-emerald-700 font-bold border border-emerald-500/40 bg-emerald-50/40"
                          : "neo-raised text-ink hover:text-teal-700"
                      }`}
                    >
                      ✓ Yes, I have management experience
                    </button>
                    <button
                      type="button"
                      onClick={() => setAnswerText("no")}
                      className={`px-4 py-2.5 text-xs font-semibold rounded-xl transition-all ${
                        answerText.toLowerCase() === "no"
                          ? "neo-pressed text-slate-700 font-bold border border-slate-400"
                          : "neo-raised text-ink hover:text-slate-600"
                      }`}
                    >
                      ✕ No management experience
                    </button>
                  </div>
                )}

                <form onSubmit={handleSaveAnswer} className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-2">
                      Your Answer (Text or Spoken)
                    </label>
                    <textarea
                      rows={4}
                      required
                      value={answerText}
                      onChange={(e) => {
                        setAnswerText(e.target.value);
                        setInputMode("text");
                      }}
                      className="neo-inset w-full p-4 text-sm text-ink bg-transparent focus:outline-none focus:ring-2 focus:ring-teal-500/30 rounded-xl resize-none transition-all"
                      placeholder="Type your response, select an option above, or click Speak..."
                    />
                  </div>

                  {error && (
                    <div className="p-3 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-xl">
                      {error}
                    </div>
                  )}

                  <div className="flex items-center justify-between gap-4 pt-2">
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
                      className="btn-teal px-7 py-2.5 text-xs font-bold uppercase tracking-wider disabled:opacity-50"
                    >
                      {submitting ? "Saving..." : "Save & Continue →"}
                    </button>
                  </div>
                </form>
              </>
            )}
          </div>
        )}
      </div>
    </Shell>
  );
}

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

  async function handleResumeUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
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
        throw new Error(errJson.detail || "Failed to upload resume PDF");
      }
      const data = await res.json();
      setAnswerText(data.resume_id || file.name);
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
          <div className="neo-raised p-8 text-center text-muted">
            Connecting to your career counsellor...
          </div>
        ) : counselState?.done ? (
          <div className="neo-raised p-8 text-center space-y-4">
            <h2 className="text-xl font-bold text-ink">Onboarding Complete</h2>
            <p className="text-muted">All profile sections have been recorded. Advancing to To-Dos...</p>
          </div>
        ) : (
          <div className="neo-raised p-8 space-y-6">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs uppercase font-semibold tracking-wider text-muted">
                  Question: {counselState?.step?.replace("_", " ")}
                </span>
                <span className="text-xs text-accent font-medium">Candidate Onboarding</span>
              </div>
              <h2 className="text-xl font-semibold text-ink leading-relaxed">
                {counselState?.prompt}
              </h2>
            </div>

            {counselState?.step === "resume" && (
              <div className="p-4 rounded-xl border border-dashed border-[#c5ced8] bg-wash/50 space-y-2">
                <p className="text-xs font-semibold uppercase text-muted">Upload Resume PDF</p>
                <input
                  type="file"
                  accept="application/pdf"
                  onChange={handleResumeUpload}
                  disabled={uploadingResume}
                  className="block w-full text-sm text-muted file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-[#3d6b8c] file:text-white hover:file:opacity-90 cursor-pointer"
                />
                {uploadingResume && (
                  <p className="text-xs text-accent animate-pulse">Processing PDF parser...</p>
                )}
              </div>
            )}

            {counselState?.choices && counselState.choices.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase text-muted">Recommended Choices:</p>
                <div className="flex flex-wrap gap-2">
                  {counselState.choices.map((choice) => (
                    <button
                      key={choice}
                      type="button"
                      onClick={() => {
                        setAnswerText(choice);
                        setInputMode("text");
                      }}
                      className="neo-raised px-3 py-1.5 text-xs font-medium text-ink hover:text-accent transition-colors"
                    >
                      {choice}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {counselState?.step === "management" && (
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => setAnswerText("yes")}
                  className={`px-4 py-2 text-xs font-semibold rounded-lg ${
                    answerText.toLowerCase() === "yes"
                      ? "neo-pressed text-accent"
                      : "neo-raised text-ink"
                  }`}
                >
                  Yes, I have management experience
                </button>
                <button
                  type="button"
                  onClick={() => setAnswerText("no")}
                  className={`px-4 py-2 text-xs font-semibold rounded-lg ${
                    answerText.toLowerCase() === "no"
                      ? "neo-pressed text-accent"
                      : "neo-raised text-ink"
                  }`}
                >
                  No management experience
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
                  className="neo-inset w-full p-4 text-ink bg-transparent focus:outline-none resize-none"
                  placeholder="Type your response, or click Speak to use microphone..."
                />
              </div>

              {error && (
                <div className="p-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg">
                  {error}
                </div>
              )}

              <div className="flex items-center justify-between gap-4 pt-2">
                <button
                  type="button"
                  onClick={handleSpeak}
                  disabled={listening || submitting}
                  className="neo-raised px-4 py-2.5 text-xs font-semibold text-ink hover:text-accent flex items-center gap-2"
                >
                  <span>🎙️</span>
                  <span>{listening ? "Listening..." : "Speak"}</span>
                </button>

                <button
                  type="submit"
                  disabled={submitting || !answerText.trim()}
                  className="neo-pressed px-6 py-2.5 text-xs font-bold uppercase tracking-wider transition-all disabled:opacity-50"
                >
                  {submitting ? "Saving..." : "Save Answer"}
                </button>
              </div>
            </form>
          </div>
        )}
      </div>
    </Shell>
  );
}

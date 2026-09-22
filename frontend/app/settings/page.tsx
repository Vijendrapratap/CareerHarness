"use client";

import React, { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { api } from "@/lib/api";

interface ApiKeyItem {
  id: string;
  provider: string;
  masked_preview: string;
  status: string;
  is_default: boolean;
  last_validated_at?: string;
}

export default function SettingsPage() {
  const [keys, setKeys] = useState<ApiKeyItem[]>([]);
  const [loadingKeys, setLoadingKeys] = useState(true);
  const [savingKey, setSavingKey] = useState(false);
  const [deletingProvider, setDeletingProvider] = useState<string | null>(null);
  const [keyError, setKeyError] = useState<string | null>(null);
  const [keySuccess, setKeySuccess] = useState<string | null>(null);

  // New Key Form
  const [selectedProvider, setSelectedProvider] = useState("openrouter");
  const [apiKeyInput, setApiKeyInput] = useState("");

  // Preferences State
  const [workArrangement, setWorkArrangement] = useState("Remote Only");
  const [targetLocation, setTargetLocation] = useState("US Remote / Tech Hubs");
  const [authorization, setAuthorization] = useState("Authorized (No Sponsorship Required)");
  const [leadershipTrack, setLeadershipTrack] = useState<"ic" | "lead">("ic");
  const [selectedDealbreakers, setSelectedDealbreakers] = useState<string[]>([
    "Legacy Monolithic Codebases",
    "Uncompensated 24/7 On-Call Rotations",
  ]);
  const [savingPrefs, setSavingPrefs] = useState(false);
  const [prefsSuccess, setPrefsSuccess] = useState<string | null>(null);

  useEffect(() => {
    loadSettings();
  }, []);

  async function loadSettings() {
    setLoadingKeys(true);
    setKeyError(null);
    try {
      // 1. Load keys
      const keysData = await api<ApiKeyItem[]>("/api/keys").catch(() => []);
      setKeys(keysData);

      // 2. Load preferences from counsel
      const counselData = await api<any>("/api/counsel").catch(() => null);
      if (counselData?.history) {
        const hMap = (counselData.history as Array<{ step: string; answer: string }>).reduce(
          (acc, item) => {
            acc[item.step] = item.answer;
            return acc;
          },
          {} as Record<string, string>
        );

        if (hMap.location) setTargetLocation(hMap.location);
        if (hMap.authorization) setAuthorization(hMap.authorization);
        if (hMap.management) {
          setLeadershipTrack(hMap.management.toLowerCase().includes("yes") ? "lead" : "ic");
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setKeyError(err.message);
      } else {
        setKeyError("Failed to load settings");
      }
    } finally {
      setLoadingKeys(false);
    }
  }

  async function handleRegisterKey(e: React.FormEvent) {
    e.preventDefault();
    if (!apiKeyInput.trim()) return;

    setKeyError(null);
    setKeySuccess(null);
    setSavingKey(true);
    try {
      const res = await api<ApiKeyItem>("/api/keys", {
        method: "POST",
        body: JSON.stringify({
          provider: selectedProvider,
          api_key: apiKeyInput.trim(),
          is_default: true,
        }),
      });

      setKeys((prev) => {
        const filtered = prev.filter((k) => k.provider !== res.provider);
        return [...filtered, res];
      });

      setApiKeyInput("");
      setKeySuccess(`Successfully validated and stored ${res.provider} key in vault.`);
      setTimeout(() => setKeySuccess(null), 4000);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setKeyError(err.message);
      } else {
        setKeyError("Failed to register API key");
      }
    } finally {
      setSavingKey(false);
    }
  }

  async function handleDeleteKey(provider: string) {
    setKeyError(null);
    setDeletingProvider(provider);
    try {
      await api(`/api/keys/${provider}`, { method: "DELETE" });
      setKeys((prev) => prev.filter((k) => k.provider !== provider));
      setKeySuccess(`Removed ${provider} key from envelope-encrypted vault.`);
      setTimeout(() => setKeySuccess(null), 3000);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setKeyError(err.message);
      } else {
        setKeyError("Failed to delete key");
      }
    } finally {
      setDeletingProvider(null);
    }
  }

  async function handleSavePreferences(e: React.FormEvent) {
    e.preventDefault();
    setSavingPrefs(true);
    setPrefsSuccess(null);
    try {
      await api("/api/counsel/preferences", {
        method: "POST",
        body: JSON.stringify({
          work_arrangement: workArrangement,
          location: targetLocation,
          authorization,
          management: leadershipTrack === "lead",
          dealbreakers: selectedDealbreakers,
          preferences: `Prefers ${workArrangement} in ${targetLocation}. Visa: ${authorization}`,
        }),
      });

      setPrefsSuccess("Search preferences updated successfully!");
      setTimeout(() => setPrefsSuccess(null), 3500);
    } catch (err: unknown) {
      setKeyError(err instanceof Error ? err.message : "Failed to update preferences");
    } finally {
      setSavingPrefs(false);
    }
  }

  function toggleDealbreaker(item: string) {
    setSelectedDealbreakers((prev) =>
      prev.includes(item) ? prev.filter((d) => d !== item) : [...prev, item]
    );
  }

  return (
    <Shell title="Settings & Vault Configuration">
      <div className="space-y-8">
        {/* Header Hero */}
        <div className="neo-raised p-6 rounded-2xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="h-12 w-12 rounded-2xl bg-gradient-to-br from-teal-600 to-cyan-600 text-white flex items-center justify-center text-xl shadow-md">
              ⚙️
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs uppercase tracking-wider font-bold text-teal-800">
                  Platform Configuration
                </span>
                <span className="badge-teal text-[10px] py-0.5 px-2">Zero Platform Key Fallback</span>
              </div>
              <h2 className="text-lg font-bold text-ink">BYOK Key Vault & Search Preferences</h2>
            </div>
          </div>

          <div className="flex items-center gap-2 text-xs">
            <span className="badge-emerald text-[11px] py-1 px-3">
              ✓ Envelope Encryption (AES-256-GCM)
            </span>
          </div>
        </div>

        {keyError && (
          <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-medium flex items-center justify-between">
            <span>{keyError}</span>
            <button onClick={() => setKeyError(null)} className="text-rose-600 font-bold ml-4">
              ✕
            </button>
          </div>
        )}

        {keySuccess && (
          <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-medium flex items-center justify-between">
            <span>{keySuccess}</span>
            <button onClick={() => setKeySuccess(null)} className="text-emerald-600 font-bold ml-4">
              ✕
            </button>
          </div>
        )}

        {/* 2-Column Responsive Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Left Column (7 cols): BYOK Key Vault */}
          <div className="lg:col-span-7 space-y-6">
            {/* Registered Keys List */}
            <div className="neo-card p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-slate-200/80 pb-3">
                <div>
                  <h3 className="text-sm font-bold uppercase tracking-wider text-ink">
                    Registered Provider Keys (BYOK)
                  </h3>
                  <p className="text-xs text-muted">
                    Keys are stored envelope-encrypted with AES-256-GCM and zeroized in-memory after calls.
                  </p>
                </div>
                <span className="badge-cyan text-[10px] py-0.5 px-2">{keys.length} Registered</span>
              </div>

              {loadingKeys ? (
                <div className="p-6 text-center text-xs text-muted">
                  <div className="inline-block h-5 w-5 border-2 border-teal-600 border-t-transparent rounded-full animate-spin mb-2" />
                  <p>Loading credentials from key vault...</p>
                </div>
              ) : keys.length === 0 ? (
                <div className="p-6 rounded-xl border border-dashed border-slate-300 text-center text-xs text-muted space-y-1">
                  <p className="font-semibold text-ink">No provider API keys stored yet.</p>
                  <p>Register your OpenRouter, OpenAI, Anthropic, or Gemini key below to power autonomous scouting and tailored outreach.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {keys.map((k) => {
                    const providerTheme =
                      k.provider.toLowerCase() === "openai"
                        ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                        : k.provider.toLowerCase() === "anthropic"
                        ? "bg-amber-50 text-amber-800 border-amber-200"
                        : k.provider.toLowerCase() === "gemini"
                        ? "bg-sky-50 text-sky-800 border-sky-200"
                        : "bg-teal-50 text-teal-800 border-teal-200";

                    return (
                      <div
                        key={k.id}
                        className="p-4 rounded-xl neo-raised bg-white/90 flex items-center justify-between gap-4 border border-slate-200/80 transition-all hover:border-teal-300/60"
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span
                              className={`text-xs font-bold uppercase tracking-wide px-2.5 py-0.5 rounded-md border ${providerTheme}`}
                            >
                              {k.provider}
                            </span>
                            <span
                              className={
                                k.status === "active"
                                  ? "badge-emerald text-[10px] py-0.5 px-2 flex items-center gap-1"
                                  : "badge-bronze text-[10px] py-0.5 px-2"
                              }
                            >
                              {k.status === "active" && (
                                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                              )}
                              {k.status}
                            </span>
                            {k.is_default && (
                              <span className="badge-teal text-[10px] py-0.5 px-2">Primary</span>
                            )}
                          </div>
                          <p className="text-xs font-mono text-muted">{k.masked_preview}</p>
                        </div>

                        <button
                          type="button"
                          onClick={() => handleDeleteKey(k.provider)}
                          disabled={deletingProvider === k.provider}
                          className="text-xs text-rose-600 hover:text-rose-800 font-semibold px-3 py-1.5 rounded-lg hover:bg-rose-50 border border-transparent hover:border-rose-200 transition-all disabled:opacity-50 active:scale-[0.97]"
                        >
                          {deletingProvider === k.provider ? "Purging..." : "Remove"}
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Add / Rotate Key Form */}
            <div className="neo-card p-6 space-y-4">
              <div className="border-b border-slate-200/80 pb-3">
                <h3 className="text-sm font-bold uppercase tracking-wider text-ink">
                  Register or Rotate API Key
                </h3>
                <p className="text-xs text-muted">
                  The key is validated immediately against upstream provider probe endpoints.
                </p>
              </div>

              <form onSubmit={handleRegisterKey} className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-1.5">
                      Provider
                    </label>
                    <select
                      value={selectedProvider}
                      onChange={(e) => setSelectedProvider(e.target.value)}
                      className="neo-inset w-full px-4 py-2.5 text-xs text-ink bg-transparent focus:outline-none focus:ring-2 focus:ring-teal-500/30 rounded-xl"
                    >
                      <option value="openrouter">OpenRouter</option>
                      <option value="openai">OpenAI</option>
                      <option value="anthropic">Anthropic</option>
                      <option value="gemini">Google Gemini</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-1.5">
                      API Key
                    </label>
                    <input
                      type="password"
                      required
                      value={apiKeyInput}
                      onChange={(e) => setApiKeyInput(e.target.value)}
                      placeholder="sk-or-v1-..."
                      className="neo-inset w-full px-4 py-2.5 text-xs text-ink bg-transparent focus:outline-none focus:ring-2 focus:ring-teal-500/30 rounded-xl font-mono"
                    />
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2">
                  <p className="text-[11px] text-muted">
                    🔐 Keys never touch server logs or third-party monitoring.
                  </p>
                  <button
                    type="submit"
                    disabled={savingKey || !apiKeyInput.trim()}
                    className="btn-teal px-6 py-2.5 text-xs font-bold uppercase tracking-wider disabled:opacity-50 shadow-md"
                  >
                    {savingKey ? "Probing & Vaulting..." : "Validate & Save Key →"}
                  </button>
                </div>
              </form>
            </div>
          </div>

          {/* Right Column (5 cols): Search Preferences & Account Controls */}
          <div className="lg:col-span-5 space-y-6">
            <div className="neo-card p-6 space-y-5">
              <div className="flex items-center justify-between border-b border-slate-200/80 pb-3">
                <div>
                  <h3 className="text-sm font-bold uppercase tracking-wider text-ink">
                    Search & Matching Preferences
                  </h3>
                  <p className="text-xs text-muted">
                    Calibrates Scout&apos;s automated 2-hour job discovery cycle.
                  </p>
                </div>
                {prefsSuccess && (
                  <span className="badge-emerald text-[10px] py-0.5 px-2 animate-pulse">
                    ✓ Saved
                  </span>
                )}
              </div>

              <form onSubmit={handleSavePreferences} className="space-y-4">
                {/* Work Arrangement */}
                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-muted">
                    Work Arrangement
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {[
                      { id: "Remote Only", activeColor: "bg-teal-600 text-white shadow-sm shadow-teal-600/30" },
                      { id: "Hybrid", activeColor: "bg-sky-600 text-white shadow-sm shadow-sky-600/30" },
                      { id: "On-site", activeColor: "bg-amber-600 text-white shadow-sm shadow-amber-600/30" },
                    ].map((opt) => (
                      <button
                        key={opt.id}
                        type="button"
                        onClick={() => setWorkArrangement(opt.id)}
                        className={`px-3.5 py-1.5 text-xs rounded-xl font-bold transition-all active:scale-[0.97] ${
                          workArrangement === opt.id
                            ? `${opt.activeColor} ring-1 ring-white/20`
                            : "neo-raised text-muted hover:text-ink bg-white/60"
                        }`}
                      >
                        {opt.id}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Target Locations */}
                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-muted">
                    Location Preference
                  </label>
                  <input
                    type="text"
                    value={targetLocation}
                    onChange={(e) => setTargetLocation(e.target.value)}
                    placeholder="e.g. US Remote, San Francisco, New York..."
                    className="neo-inset w-full px-4 py-2.5 text-xs text-ink bg-transparent focus:outline-none focus:ring-2 focus:ring-sky-500/30 rounded-xl"
                  />
                </div>

                {/* Work Authorization */}
                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-muted">
                    Work Authorization
                  </label>
                  <select
                    value={authorization}
                    onChange={(e) => setAuthorization(e.target.value)}
                    className="neo-inset w-full px-4 py-2.5 text-xs text-ink bg-transparent focus:outline-none focus:ring-2 focus:ring-emerald-500/30 rounded-xl"
                  >
                    <option value="Authorized (No Sponsorship Required)">
                      Authorized (Citizen / PR, No Sponsorship)
                    </option>
                    <option value="Requires Visa Sponsorship (H-1B, etc.)">
                      Requires Visa Sponsorship (H-1B, Skilled Worker)
                    </option>
                    <option value="Authorized via OPT / STEM OPT">
                      Authorized via OPT / STEM OPT
                    </option>
                    <option value="Open to Independent Contractor / B2B">
                      Open to Independent Contractor / B2B
                    </option>
                  </select>
                </div>

                {/* Career Track */}
                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-muted">
                    Career Track
                  </label>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setLeadershipTrack("ic")}
                      className={`flex-1 py-2 px-3 text-xs rounded-xl font-bold transition-all active:scale-[0.97] ${
                        leadershipTrack === "ic"
                          ? "bg-teal-600 text-white shadow-sm shadow-teal-600/30 ring-1 ring-white/20"
                          : "neo-raised text-muted hover:text-ink bg-white/60"
                      }`}
                    >
                      Senior / Staff IC
                    </button>
                    <button
                      type="button"
                      onClick={() => setLeadershipTrack("lead")}
                      className={`flex-1 py-2 px-3 text-xs rounded-xl font-bold transition-all active:scale-[0.97] ${
                        leadershipTrack === "lead"
                          ? "bg-amber-600 text-white shadow-sm shadow-amber-600/30 ring-1 ring-white/20"
                          : "neo-raised text-muted hover:text-ink bg-white/60"
                      }`}
                    >
                      Lead / Manager
                    </button>
                  </div>
                </div>

                {/* Dealbreakers */}
                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-muted">
                    Dealbreakers to Exclude
                  </label>
                  <div className="flex flex-wrap gap-1.5">
                    {[
                      "Legacy Monolithic Codebases",
                      "Uncompensated 24/7 On-Call Rotations",
                      "Excessive Meeting Overhead",
                      "Mandatory 5-Day Office Requirements",
                    ].map((d) => (
                      <button
                        key={d}
                        type="button"
                        onClick={() => toggleDealbreaker(d)}
                        className={`px-2.5 py-1 text-[11px] rounded-lg transition-all active:scale-[0.97] ${
                          selectedDealbreakers.includes(d)
                            ? "bg-rose-50 text-rose-800 border border-rose-300 font-bold shadow-sm"
                            : "neo-raised text-muted hover:text-ink hover:border-slate-300"
                        }`}
                      >
                        {selectedDealbreakers.includes(d) ? `✕ ${d}` : `+ ${d}`}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="pt-3 border-t border-slate-200/80 flex justify-end">
                  <button
                    type="submit"
                    disabled={savingPrefs}
                    className="btn-teal px-6 py-2.5 text-xs font-bold uppercase tracking-wider disabled:opacity-50 shadow-md active:scale-[0.97]"
                  >
                    {savingPrefs ? "Saving..." : "Save Preferences →"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      </div>
    </Shell>
  );
}

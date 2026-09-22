"use client";

import React, { useState } from "react";
import { Shell } from "@/components/Shell";
import { api } from "@/lib/api";

export default function MailboxPage() {
  const [emailAddress, setEmailAddress] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [refreshToken, setRefreshToken] = useState("");
  const [provider, setProvider] = useState("gmail");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      // 1. Connect mailbox
      await api("/api/emails/connect", {
        method: "POST",
        body: JSON.stringify({
          email_address: emailAddress.trim(),
          access_token: accessToken.trim(),
          refresh_token: refreshToken.trim(),
          provider,
        }),
      });

      // 2. Grant explicit consent
      await api("/api/emails/consent", {
        method: "POST",
        body: JSON.stringify({}),
      });

      // 3. Update journey stage to hunt
      await api("/api/journey/stage", {
        method: "POST",
        body: JSON.stringify({ stage: "hunt" }),
      });

      // 4. Navigate to jobs board
      window.location.assign("/jobs");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to connect mailbox");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <Shell title="Connect Mailbox">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Form Card (7 cols) */}
        <div className="lg:col-span-7 neo-card p-6 sm:p-8 space-y-6">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="badge-teal text-[10px] py-0.5 px-2 font-bold">
                Mailbox Integration
              </span>
              <span className="badge-emerald text-[10px] py-0.5 px-2">
                AES-256 Envelope Encrypted
              </span>
            </div>
            <h2 className="text-xl font-bold text-ink tracking-tight">Connect Your Application Mailbox</h2>
            <p className="text-xs text-muted leading-relaxed">
              The autonomous hunter sends application emails from this mailbox only after you review and approve each message packet in your dashboard.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-1.5">
                Email Provider
              </label>
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                className="neo-inset w-full px-4 py-3 text-sm text-ink bg-transparent focus:outline-none focus:ring-2 focus:ring-teal-500/30 rounded-xl transition-all"
              >
                <option value="gmail">Google Gmail</option>
                <option value="outlook">Microsoft Outlook</option>
                <option value="smtp">Custom SMTP</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-1.5">
                Email Address
              </label>
              <input
                type="email"
                required
                value={emailAddress}
                onChange={(e) => setEmailAddress(e.target.value)}
                className="neo-inset w-full px-4 py-3 text-sm text-ink bg-transparent focus:outline-none focus:ring-2 focus:ring-teal-500/30 rounded-xl transition-all"
                placeholder="you@company.com"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-1.5">
                OAuth Access Token
              </label>
              <input
                type="password"
                required
                value={accessToken}
                onChange={(e) => setAccessToken(e.target.value)}
                className="neo-inset w-full px-4 py-3 text-ink bg-transparent focus:outline-none focus:ring-2 focus:ring-teal-500/30 rounded-xl font-mono text-xs transition-all"
                placeholder="Access token (decrypted in worker memory only)"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-1.5">
                OAuth Refresh Token
              </label>
              <input
                type="password"
                required
                value={refreshToken}
                onChange={(e) => setRefreshToken(e.target.value)}
                className="neo-inset w-full px-4 py-3 text-ink bg-transparent focus:outline-none focus:ring-2 focus:ring-teal-500/30 rounded-xl font-mono text-xs transition-all"
                placeholder="OAuth refresh token"
              />
            </div>

            {error && (
              <div className="p-3 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-xl">
                {error}
              </div>
            )}

            <div className="pt-2">
              <button
                type="submit"
                disabled={loading}
                className="btn-teal w-full py-3.5 text-xs font-bold uppercase tracking-wider disabled:opacity-50"
              >
                {loading ? "Connecting & Verifying..." : "Connect & Continue to Scouted Jobs →"}
              </button>
            </div>
          </form>
        </div>

        {/* Security & Safeguards Card (5 cols) */}
        <div className="lg:col-span-5 space-y-5">
          <div className="neo-card p-6 space-y-4 border border-teal-500/20 bg-gradient-to-br from-white/90 to-teal-50/20">
            <div className="flex items-center gap-2">
              <span className="badge-teal text-[10px] py-0.5 px-2 font-bold">Safety Mandate</span>
              <h3 className="text-xs font-bold text-ink uppercase tracking-wider">Human-in-the-Loop Protocol</h3>
            </div>
            <div className="space-y-3 text-xs text-muted">
              <div className="p-3.5 rounded-xl neo-inset bg-white/60 space-y-1">
                <p className="font-bold text-ink flex items-center gap-1.5">
                  <span>🛡️</span> Zero Unapproved Outbound
                </p>
                <p className="text-[11px] leading-relaxed">
                  CareerHarness will never send cold outreach or job applications autonomously without your explicit click on the Front-Face dashboard.
                </p>
              </div>
              <div className="p-3.5 rounded-xl neo-inset bg-white/60 space-y-1">
                <p className="font-bold text-ink flex items-center gap-1.5">
                  <span>🔐</span> Envelope Encryption
                </p>
                <p className="text-[11px] leading-relaxed">
                  Tokens are stored using AES-256-GCM symmetric encryption with rotating key derivation. Decrypted strictly within local process memory.
                </p>
              </div>
              <div className="p-3.5 rounded-xl neo-inset bg-white/60 space-y-1">
                <p className="font-bold text-ink flex items-center gap-1.5">
                  <span>📥</span> Inbound Reply Syncing
                </p>
                <p className="text-[11px] leading-relaxed">
                  Replies from recruiters automatically populate the Recruiter Inbox so you never miss an interview invite or technical screening.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Shell>
  );
}

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
      <div className="max-w-xl mx-auto space-y-6">
        <div className="neo-raised p-8 space-y-6">
          <div className="space-y-2">
            <span className="text-xs uppercase font-semibold tracking-wider text-muted">
              Step 3: Mailbox Connection
            </span>
            <h2 className="text-xl font-bold text-ink">Connect Your Application Mailbox</h2>
            <p className="text-sm text-muted">
              The agent sends from this mailbox only after you approve a message.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-1">
                Email Provider
              </label>
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                className="neo-inset w-full px-4 py-3 text-ink bg-transparent focus:outline-none"
              >
                <option value="gmail">Google Gmail</option>
                <option value="outlook">Microsoft Outlook</option>
                <option value="smtp">Custom SMTP</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-1">
                Email Address
              </label>
              <input
                type="email"
                required
                value={emailAddress}
                onChange={(e) => setEmailAddress(e.target.value)}
                className="neo-inset w-full px-4 py-3 text-ink bg-transparent focus:outline-none"
                placeholder="you@company.com"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-1">
                Access Token
              </label>
              <input
                type="password"
                required
                value={accessToken}
                onChange={(e) => setAccessToken(e.target.value)}
                className="neo-inset w-full px-4 py-3 text-ink bg-transparent focus:outline-none font-mono text-xs"
                placeholder="OAuth access token (envelope encrypted)"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-1">
                Refresh Token
              </label>
              <input
                type="password"
                required
                value={refreshToken}
                onChange={(e) => setRefreshToken(e.target.value)}
                className="neo-inset w-full px-4 py-3 text-ink bg-transparent focus:outline-none font-mono text-xs"
                placeholder="OAuth refresh token"
              />
            </div>

            {error && (
              <div className="p-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg">
                {error}
              </div>
            )}

            <div className="pt-2">
              <button
                type="submit"
                disabled={loading}
                className="neo-pressed w-full py-3 text-xs font-bold uppercase tracking-wider text-accent transition-all disabled:opacity-50"
              >
                {loading ? "Connecting & Verifying..." : "Connect & Continue to Jobs →"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Shell>
  );
}

"use client";

import React, { useState } from "react";
import Link from "next/link";
import { LogoMark } from "@/components/Logo";
import { api, goToCurrentStage } from "@/lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      await goToCurrentStage();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to sign in");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12 bg-wash">
      <div className="neo-card w-full max-w-md p-8 relative overflow-hidden">
        <div className="mb-6 text-center">
          <LogoMark size={56} className="mx-auto mb-4 drop-shadow-[0_10px_18px_rgba(18,20,28,0.3)]" />
          <span className="badge-cyan text-xs font-semibold py-0.5 px-2.5">Candidate Career Platform</span>
          <h1 className="text-2xl font-bold text-ink mt-2">Sign In</h1>
          <p className="text-xs text-muted mt-1">Enter your credentials to access your candidate journey.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-1.5">
              Email Address
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="neo-inset w-full px-4 py-3 text-ink text-sm bg-transparent focus:outline-none focus:ring-2 focus:ring-teal-500/30 transition-all rounded-xl"
              placeholder="candidate@example.com"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-1.5">
              Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="neo-inset w-full px-4 py-3 text-ink text-sm bg-transparent focus:outline-none focus:ring-2 focus:ring-teal-500/30 transition-all rounded-xl"
              placeholder="••••••••"
            />
          </div>

          {error && (
            <div className="p-3 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-xl">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="btn-teal w-full py-3.5 text-sm font-semibold tracking-wide mt-3 disabled:opacity-50"
          >
            {loading ? "Signing in..." : "Sign In to Platform →"}
          </button>
        </form>

        <div className="mt-6 text-center text-xs text-muted border-t border-slate-200/60 pt-4">
          Don&apos;t have an account?{" "}
          <Link href="/register" className="text-teal-700 font-bold hover:text-teal-800 hover:underline">
            Register here
          </Link>
        </div>
      </div>
    </div>
  );
}

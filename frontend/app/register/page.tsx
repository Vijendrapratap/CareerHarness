"use client";

import React, { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

export default function RegisterPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api("/api/auth/signup", {
        method: "POST",
        body: JSON.stringify({ email, password, name }),
      });
      window.location.assign("/counsel");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Registration failed");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12 bg-wash">
      <div className="neo-card w-full max-w-md p-8 relative overflow-hidden">
        <div className="mb-6 text-center">
          <div className="mx-auto h-12 w-12 rounded-2xl bg-gradient-to-br from-teal-600 to-cyan-700 flex items-center justify-center text-white font-bold text-xl shadow-lg shadow-teal-600/20 mb-3 border border-teal-400/40">
            CH
          </div>
          <span className="badge-teal text-xs font-semibold py-0.5 px-2.5">Candidate Registration</span>
          <h1 className="text-2xl font-bold text-ink mt-2">Create Account</h1>
          <p className="text-xs text-muted mt-1">Begin your guided candidate career journey with DeepSeek AI.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-1.5">
              Full Name
            </label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="neo-inset w-full px-4 py-3 text-ink text-sm bg-transparent focus:outline-none focus:ring-2 focus:ring-teal-500/30 transition-all rounded-xl"
              placeholder="Ada Lovelace"
            />
          </div>

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
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="neo-inset w-full px-4 py-3 text-ink text-sm bg-transparent focus:outline-none focus:ring-2 focus:ring-teal-500/30 transition-all rounded-xl"
              placeholder="Minimum 8 characters"
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
            {loading ? "Creating Account..." : "Create Account & Start Journey →"}
          </button>
        </form>

        <div className="mt-6 text-center text-xs text-muted border-t border-slate-200/60 pt-4">
          Already have an account?{" "}
          <Link href="/login" className="text-teal-700 font-bold hover:text-teal-800 hover:underline">
            Sign In here
          </Link>
        </div>
      </div>
    </div>
  );
}

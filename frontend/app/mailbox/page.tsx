"use client";

import React, { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { api } from "@/lib/api";

type Provider = "gmail" | "outlook";

interface EmailStatus {
  providers: Record<Provider, boolean>;
  connected: { email: string; provider: Provider } | null;
}

const PROVIDERS: { id: Provider; label: string; mark: string; markClass: string }[] = [
  { id: "gmail", label: "Connect Gmail", mark: "G", markClass: "bg-white text-rose-600 border border-slate-200" },
  { id: "outlook", label: "Connect Outlook", mark: "O", markClass: "bg-sky-600 text-white" },
];

const FAQ = [
  {
    q: "How do you find the companies?",
    a: "Scout searches public company job boards for your target roles. We only draft an email when the posting lists a recruiter or hiring contact address.",
  },
  {
    q: "Which email and CV do you use?",
    a: "The inbox you connect here, and your uploaded resume — or a tailored version you approved for that job. Nothing is invented.",
  },
  {
    q: "How many go out each day?",
    a: "None without you. Every draft waits for your approval, and you can disconnect anytime. We only get permission to send — we can't read your inbox.",
  },
];

const STEPS = [
  { n: 1, title: "Scout finds a matching role", body: "A posting for your target role that lists a recruiter address." },
  { n: 2, title: "We draft a short email", body: "Written from your resume, in your voice, with your CV attached." },
  { n: 3, title: "You approve, it sends from your inbox", body: "Replies arrive straight in your own mailbox." },
];

export default function MailboxPage() {
  const [status, setStatus] = useState<EmailStatus | null>(null);
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [redirecting, setRedirecting] = useState<Provider | null>(null);
  const [disconnecting, setDisconnecting] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const connected = params.get("connected");
    const error = params.get("error");
    if (connected) setNotice({ kind: "ok", text: "Email connected. You're all set." });
    if (error) setNotice({ kind: "error", text: error });
    if (connected || error) window.history.replaceState(null, "", "/mailbox");
    loadStatus();
  }, []);

  async function loadStatus() {
    try {
      setStatus(await api<EmailStatus>("/api/emails/status"));
    } catch (err: unknown) {
      setNotice({ kind: "error", text: err instanceof Error ? err.message : "Could not load email status" });
    }
  }

  function connect(provider: Provider) {
    setRedirecting(provider);
    // Full-page navigation: the API redirects to the provider's sign-in page and back.
    window.location.assign(`/api/emails/oauth/${provider}/start`);
  }

  async function disconnect() {
    setDisconnecting(true);
    try {
      await api("/api/insights/email", { method: "DELETE" });
      setNotice({ kind: "ok", text: "Email disconnected. Nothing will be sent." });
      await loadStatus();
    } catch (err: unknown) {
      setNotice({ kind: "error", text: err instanceof Error ? err.message : "Could not disconnect" });
    } finally {
      setDisconnecting(false);
    }
  }

  const connected = status?.connected;
  const noneConfigured = status && !status.providers.gmail && !status.providers.outlook;

  return (
    <Shell title="Email Outreach">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-5 neo-card p-6 sm:p-8 space-y-6">
          <div className="space-y-2">
            <span className="badge-sky text-[10px] py-0.5 px-2 font-bold uppercase tracking-wider">Optional</span>
            <h2 className="text-2xl font-black text-ink tracking-tight leading-tight">
              We email companies hiring your role
            </h2>
            <p className="text-sm text-muted leading-relaxed">
              Sent from your own inbox, in your name — only after you approve each email.
            </p>
          </div>

          {notice && (
            <div
              role={notice.kind === "error" ? "alert" : "status"}
              className={`p-3 text-xs rounded-xl border ${
                notice.kind === "error"
                  ? "text-rose-800 bg-rose-50 border-rose-200"
                  : "text-emerald-900 bg-emerald-50 border-emerald-300"
              }`}
            >
              {notice.text}
            </div>
          )}

          {!status ? (
            <div className="h-24 rounded-xl bg-slate-100 animate-pulse" />
          ) : connected ? (
            <div className="space-y-4">
              <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-300 flex items-center gap-3">
                <span className="h-9 w-9 rounded-xl bg-emerald-500 text-white flex items-center justify-center font-bold">✓</span>
                <div className="min-w-0">
                  <p className="text-sm font-bold text-emerald-950 truncate">{connected.email}</p>
                  <p className="text-[11px] text-emerald-800">
                    Connected via {connected.provider === "gmail" ? "Gmail" : "Outlook"}
                  </p>
                </div>
              </div>
              <div className="flex flex-col sm:flex-row gap-3">
                <a href="/jobs" className="btn-teal flex-1 text-center px-6 py-3 text-xs font-bold uppercase tracking-wider">
                  Go to Jobs →
                </a>
                <button
                  type="button"
                  onClick={disconnect}
                  disabled={disconnecting}
                  className="neo-raised px-6 py-3 text-xs font-semibold text-muted hover:text-rose-700 rounded-xl disabled:opacity-50"
                >
                  {disconnecting ? "Disconnecting..." : "Disconnect"}
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {PROVIDERS.map((p) => {
                const available = status.providers[p.id];
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => connect(p.id)}
                    disabled={!available || redirecting !== null}
                    className="w-full flex items-center justify-center gap-3 px-6 py-3.5 rounded-xl bg-ink text-white text-sm font-bold shadow-md hover:opacity-90 active:scale-[0.99] transition disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <span className={`h-6 w-6 rounded-md flex items-center justify-center text-xs font-black ${p.markClass}`}>
                      {p.mark}
                    </span>
                    {redirecting === p.id ? "Opening sign-in..." : p.label}
                  </button>
                );
              })}
              {noneConfigured ? (
                <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-2.5">
                  Email sign-in isn&apos;t set up on this server yet. An admin needs to add Google/Microsoft OAuth
                  credentials. You can keep using Jobs in the meantime.
                </p>
              ) : (
                <p className="text-[11px] text-muted leading-relaxed">
                  By connecting, you let CareerHarness send the emails you approve from this address. We can&apos;t
                  read your inbox. Disconnect anytime.
                </p>
              )}
            </div>
          )}

          <div className="divide-y divide-slate-200 border-y border-slate-200">
            {FAQ.map((item) => (
              <details key={item.q} className="group py-3">
                <summary className="flex items-center justify-between cursor-pointer list-none text-sm text-ink font-medium">
                  {item.q}
                  <span className="text-muted transition-transform group-open:rotate-90">›</span>
                </summary>
                <p className="text-xs text-muted leading-relaxed mt-2">{item.a}</p>
              </details>
            ))}
          </div>

          {!connected && (
            <a href="/jobs" className="block text-center text-xs font-semibold text-muted hover:text-ink">
              Skip for now — I&apos;ll apply myself →
            </a>
          )}
        </div>

        <div className="lg:col-span-7 neo-card p-6 sm:p-8 space-y-5 bg-slate-50/80">
          <h3 className="text-xs font-bold uppercase tracking-wider text-muted">How it works</h3>
          <ol className="space-y-3">
            {STEPS.map((s) => (
              <li key={s.n} className="flex gap-3 p-4 rounded-xl bg-white border border-slate-200">
                <span className="h-7 w-7 shrink-0 rounded-lg bg-teal-700 text-white text-xs font-bold flex items-center justify-center">
                  {s.n}
                </span>
                <div>
                  <p className="text-sm font-bold text-ink">{s.title}</p>
                  <p className="text-xs text-muted mt-0.5">{s.body}</p>
                </div>
              </li>
            ))}
          </ol>
          <div className="p-4 rounded-xl bg-white border border-slate-200 space-y-2">
            <p className="text-[10px] font-bold uppercase tracking-wider text-muted">Example draft</p>
            <p className="text-xs text-ink">
              <span className="font-semibold">Subject:</span> Backend Engineer role — quick intro
            </p>
            <p className="text-xs text-muted leading-relaxed">
              Hi — I saw you&apos;re hiring a Backend Engineer. I cut API latency 40% on a gateway serving 2M
              requests a day and would love to talk. My CV is attached.
            </p>
            <div className="flex justify-end">
              <span className="badge-amber text-[10px] py-0.5 px-2 font-bold">Waiting for your approval</span>
            </div>
          </div>
        </div>
      </div>
    </Shell>
  );
}

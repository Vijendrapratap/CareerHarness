import React, { useId } from "react";

/** Carabiner with an open gate around a summit: the harness that keeps the climb safe. */
export function LogoMark({ size = 36, className = "" }: { size?: number; className?: string }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none" aria-hidden="true" className={className}>
      <defs>
        <linearGradient id={`${id}t`} x1="8" y1="4" x2="56" y2="60" gradientUnits="userSpaceOnUse">
          <stop stopColor="#1d2130" />
          <stop offset="1" stopColor="#0d0f15" />
        </linearGradient>
        <linearGradient id={`${id}r`} x1="21" y1="40" x2="41" y2="24" gradientUnits="userSpaceOnUse">
          <stop stopColor="#ff8a3d" />
          <stop offset="1" stopColor="#ff4d5e" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="16" fill={`url(#${id}t)`} />
      <path
        d="M44 15.5H26.5A10.5 10.5 0 0 0 16 26v12a10.5 10.5 0 0 0 10.5 10.5h11A10.5 10.5 0 0 0 48 38V32"
        stroke="#f3f1ec"
        strokeWidth="5"
        strokeLinecap="round"
      />
      <path d="M48 24.5 44.5 16" stroke="#2dd4bf" strokeWidth="5" strokeLinecap="round" />
      <path
        d="M22.5 40 29 31.5l3.5 4.5 5.5-8 5 12"
        stroke={`url(#${id}r)`}
        strokeWidth="4.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function Logo({ size = 36 }: { size?: number }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <LogoMark size={size} className="drop-shadow-[0_6px_10px_rgba(18,20,28,0.25)]" />
      <span className="font-display text-[1.15rem] leading-none tracking-tight text-ink">
        <span className="font-medium">Career</span>
        <span className="font-extrabold">Harness</span>
      </span>
    </span>
  );
}

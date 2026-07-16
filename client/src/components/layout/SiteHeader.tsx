"use client";

import { useEffect, useState } from "react";
import { LogOut } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { formatClock, formatDate } from "@/lib/utils";
import { StatusDot } from "@/components/ui/StatusDot";

type Tone = "online" | "degraded" | "offline";

export function SiteHeader() {
  const { identity, logout } = useAuth();
  const [now, setNow] = useState<Date | null>(null);
  const [tone, setTone] = useState<Tone>("degraded");
  const [detail, setDetail] = useState("CONNECTING...");

  useEffect(() => {
    setNow(new Date());
    const clock = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(clock);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const health = await api.health();
        if (cancelled) return;
        setTone(health.status === "ok" ? "online" : "degraded");
        setDetail(
          `${health.active_detectors.length}/${health.configured_detectors.length} DETECTORS ACTIVE`,
        );
      } catch {
        if (cancelled) return;
        setTone("offline");
        setDetail("BACKEND UNREACHABLE");
      }
    }

    poll();
    const interval = setInterval(poll, 8000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <header className="relative z-40 flex items-center justify-between border-b border-line bg-void/80 px-6 py-4 backdrop-blur-sm">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center border border-amber">
          <svg viewBox="0 0 24 24" className="h-5 w-5 text-amber" fill="none">
            <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.4" />
            <circle cx="12" cy="12" r="2.4" fill="currentColor" />
            <path d="M12 2V5M12 19V22M2 12H5M19 12H22" stroke="currentColor" strokeWidth="1.4" />
          </svg>
        </div>
        <div className="leading-tight">
          <p className="font-display text-lg font-bold uppercase tracking-[0.14em] text-bone">
            SENTINEL <span className="text-amber">{"// "}</span>
            <span className="text-dim">Detect</span>
          </p>
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-dim">
            Console build v0.1.0 — internal use only
          </p>
        </div>
      </div>

      <div className="flex items-center gap-6">
        <div className="hidden flex-col items-end leading-tight sm:flex">
          <span className="font-mono text-xs text-bone">{now ? formatClock(now) : "--:--:-- UTC"}</span>
          <span className="font-mono text-[10px] text-dim">{now ? formatDate(now) : "----‑--‑--"}</span>
        </div>
        <div className="flex items-center gap-2 border border-line px-3 py-1.5">
          <StatusDot tone={tone} />
          <span className="font-mono text-[10px] uppercase tracking-wider text-dim">{detail}</span>
        </div>
        {identity && (
          <div className="flex items-center gap-3 border-l border-line pl-6">
            <div className="text-right leading-tight">
              <p className="font-mono text-xs text-bone">{identity.username}</p>
              <p className="font-mono text-[10px] uppercase tracking-wider text-amber">
                {identity.role}
              </p>
            </div>
            <button
              type="button"
              onClick={logout}
              title="Log out"
              className="flex h-8 w-8 items-center justify-center border border-line text-dim transition-colors hover:border-alert hover:text-alert"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>
    </header>
  );
}

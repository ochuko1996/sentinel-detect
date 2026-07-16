"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError, wsUrl } from "@/lib/api";
import type { EventSummary, EventWsMessage } from "@/lib/types";
import { formatTimestamp } from "@/lib/utils";
import { DecodeText } from "@/components/ui/DecodeText";
import { TerminalPanel } from "@/components/ui/TerminalPanel";
import { StatusDot } from "@/components/ui/StatusDot";

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<EventSummary[]>([]);
  const [live, setLive] = useState<EventWsMessage[]>([]);
  const [wsOpen, setWsOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seen = useRef<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const result = await api.listAlerts(100);
        if (cancelled) return;
        setAlerts(result);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.detail : "Failed to load alerts.");
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const ws = new WebSocket(wsUrl("/ws/alerts"));
    ws.onopen = () => setWsOpen(true);
    ws.onclose = () => setWsOpen(false);
    ws.onerror = () => setWsOpen(false);
    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as EventWsMessage;
        if (seen.current.has(message.id)) return;
        seen.current.add(message.id);
        setLive((prev) => [message, ...prev].slice(0, 100));
      } catch {
        // malformed frame — ignore
      }
    };
    return () => ws.close();
  }, []);

  const combined = [...live, ...alerts.filter((a) => !live.some((l) => l.message === a.message && l.timestamp === a.timestamp))];

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.3em] text-amber">
            Dispatch Log
          </p>
          <h1 className="font-display text-4xl font-black uppercase tracking-tight text-bone sm:text-5xl">
            <DecodeText text="Alerts" />
          </h1>
          <p className="mt-2 max-w-2xl font-mono text-sm text-dim">
            Live feed via WS /ws/alerts, backfilled with the in-memory REST
            store&apos;s recent history on load.
          </p>
        </div>
        <div className="flex items-center gap-2 border border-line px-3 py-1.5">
          <StatusDot tone={wsOpen ? "online" : "offline"} />
          <span className="font-mono text-[10px] uppercase tracking-wider text-dim">
            LIVE FEED {wsOpen ? "CONNECTED" : "DISCONNECTED"}
          </span>
        </div>
      </div>

      {error && (
        <div className="border border-alert/60 bg-alert/10 px-4 py-3 font-mono text-xs text-alert">
          {error}
        </div>
      )}

      <TerminalPanel title="Alert Stream" windowId="ALERT-LOG">
        {combined.length === 0 ? (
          <p className="font-mono text-xs text-dim">No alerts dispatched yet.</p>
        ) : (
          <table className="w-full border-collapse font-mono text-xs">
            <thead>
              <tr className="border-b border-line text-left text-dim">
                <th className="pb-2 font-normal uppercase tracking-wider">Type</th>
                <th className="pb-2 font-normal uppercase tracking-wider">Severity</th>
                <th className="pb-2 font-normal uppercase tracking-wider">Message</th>
                <th className="pb-2 font-normal uppercase tracking-wider">Time</th>
              </tr>
            </thead>
            <tbody>
              {combined.map((alert, i) => (
                <tr key={i} className="border-b border-line/50 text-bone">
                  <td className="py-2 pr-4">{alert.type}</td>
                  <td className="py-2 pr-4">
                    <span
                      className={
                        alert.severity === "critical"
                          ? "text-alert"
                          : alert.severity === "warning"
                            ? "text-amber"
                            : "text-dim"
                      }
                    >
                      {alert.severity.toUpperCase()}
                    </span>
                  </td>
                  <td className="py-2 pr-4 text-dim">{alert.message}</td>
                  <td className="py-2 text-dim">{formatTimestamp(alert.timestamp)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </TerminalPanel>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { EventSummary } from "@/lib/types";
import { formatTimestamp } from "@/lib/utils";
import { DecodeText } from "@/components/ui/DecodeText";
import { TerminalPanel } from "@/components/ui/TerminalPanel";
import { Button } from "@/components/ui/Button";

export default function EventsPage() {
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [cameraId, setCameraId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function load(filter?: string) {
    setLoading(true);
    try {
      const result = await api.listEvents({ cameraId: filter || undefined, limit: 100 });
      setEvents(result);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load events.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="space-y-8">
      <div>
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-amber">
          Rule Engine Log
        </p>
        <h1 className="font-display text-4xl font-black uppercase tracking-tight text-bone sm:text-5xl">
          <DecodeText text="Events" />
        </h1>
        <p className="mt-2 max-w-2xl font-mono text-sm text-dim">
          Every occurrence the rule engine has raised — person/vehicle/weapon
          detected, loitering, restricted-area intrusion, and the rest of the
          twelve built-in rules.
        </p>
      </div>

      <div className="flex gap-3">
        <input
          value={cameraId}
          onChange={(e) => setCameraId(e.target.value)}
          placeholder="Filter by camera_id..."
          className="w-64 border border-line bg-panel-raised px-3 py-2 font-mono text-sm text-bone outline-none focus:border-amber"
        />
        <Button variant="ghost" onClick={() => load(cameraId)}>
          Apply Filter
        </Button>
        {cameraId && (
          <Button
            variant="ghost"
            onClick={() => {
              setCameraId("");
              load();
            }}
          >
            Clear
          </Button>
        )}
      </div>

      {error && (
        <div className="border border-alert/60 bg-alert/10 px-4 py-3 font-mono text-xs text-alert">
          {error}
        </div>
      )}

      <TerminalPanel title="Event Log" windowId="EVT-LOG">
        {loading ? (
          <p className="font-mono text-xs text-dim">Loading...</p>
        ) : events.length === 0 ? (
          <p className="font-mono text-xs text-dim">No events found.</p>
        ) : (
          <table className="w-full border-collapse font-mono text-xs">
            <thead>
              <tr className="border-b border-line text-left text-dim">
                <th className="pb-2 font-normal uppercase tracking-wider">Type</th>
                <th className="pb-2 font-normal uppercase tracking-wider">Severity</th>
                <th className="pb-2 font-normal uppercase tracking-wider">Rule</th>
                <th className="pb-2 font-normal uppercase tracking-wider">Message</th>
                <th className="pb-2 font-normal uppercase tracking-wider">Time</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event, i) => (
                <tr key={i} className="border-b border-line/50 text-bone">
                  <td className="py-2 pr-4">{event.type}</td>
                  <td className="py-2 pr-4">
                    <span
                      className={
                        event.severity === "critical"
                          ? "text-alert"
                          : event.severity === "warning"
                            ? "text-amber"
                            : "text-dim"
                      }
                    >
                      {event.severity.toUpperCase()}
                    </span>
                  </td>
                  <td className="py-2 pr-4 text-dim">{event.rule}</td>
                  <td className="py-2 pr-4 text-dim">{event.message}</td>
                  <td className="py-2 text-dim">{formatTimestamp(event.timestamp)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </TerminalPanel>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { api, ApiError } from "@/lib/api";
import type { EventSummary, HealthResponse, StreamStatusResponse } from "@/lib/types";
import { DecodeText } from "@/components/ui/DecodeText";
import { TerminalPanel } from "@/components/ui/TerminalPanel";
import { StatReadout } from "@/components/ui/StatReadout";
import { formatTimestamp } from "@/lib/utils";

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } },
};
const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" as const } },
};

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [streams, setStreams] = useState<StreamStatusResponse[]>([]);
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [h, s, e] = await Promise.all([
          api.health(),
          api.listStreams(),
          api.listEvents({ limit: 8 }),
        ]);
        if (cancelled) return;
        setHealth(h);
        setStreams(s);
        setEvents(e);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.detail : "Unknown error contacting backend.");
      }
    }
    load();
    const interval = setInterval(load, 8000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <motion.div variants={container} initial="hidden" animate="show" className="space-y-8">
      <motion.div variants={item}>
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-amber">
          Operations Overview
        </p>
        <h1 className="font-display text-4xl font-black uppercase tracking-tight text-bone sm:text-5xl">
          <DecodeText text="Command Center" />
        </h1>
        <p className="mt-2 max-w-2xl font-mono text-sm text-dim">
          Live status of the SENTINEL Detect pipeline: detection, tracking, the
          rule engine, and alert delivery, across every registered camera.
        </p>
      </motion.div>

      {error && (
        <motion.div
          variants={item}
          className="border border-alert/60 bg-alert/10 px-4 py-3 font-mono text-xs text-alert"
        >
          CONNECTION FAULT — {error}
        </motion.div>
      )}

      <motion.div variants={item} className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <StatReadout label="System Status" value={health ? health.status.toUpperCase() : "…"} />
        <StatReadout
          label="Detectors"
          value={health ? `${health.active_detectors.length}/${health.configured_detectors.length}` : "…"}
          sub="active / configured"
        />
        <StatReadout
          label="Event Rules"
          value={health ? String(health.enabled_event_rules.length) : "…"}
        />
        <StatReadout
          label="Alert Channels"
          value={health ? `${health.active_alert_channels.length}/${health.configured_alert_channels.length}` : "…"}
          sub="active / configured"
        />
        <StatReadout label="Live Streams" value={String(streams.length)} />
      </motion.div>

      <motion.div variants={item} className="grid gap-4 lg:grid-cols-3">
        <Link href="/cameras" className="group">
          <TerminalPanel title="Cameras" accent="amber" className="h-full transition-colors group-hover:border-amber">
            <p className="font-mono text-xs text-dim">
              Register a camera and start a live stream — webcam, USB, RTSP, IP
              camera, or a polled directory of images.
            </p>
            <span className="mt-4 inline-block font-display text-xs uppercase tracking-[0.16em] text-amber">
              Manage cameras →
            </span>
          </TerminalPanel>
        </Link>
        <Link href="/detect" className="group">
          <TerminalPanel title="Detect" accent="amber" className="h-full transition-colors group-hover:border-amber">
            <p className="font-mono text-xs text-dim">
              Upload a single image or a video file to run the full
              detection/tracking/event pipeline against it.
            </p>
            <span className="mt-4 inline-block font-display text-xs uppercase tracking-[0.16em] text-amber">
              Run detection →
            </span>
          </TerminalPanel>
        </Link>
        <Link href="/alerts" className="group">
          <TerminalPanel title="Alerts" accent="amber" className="h-full transition-colors group-hover:border-amber">
            <p className="font-mono text-xs text-dim">
              Live feed of every alert dispatched by the rule engine, pushed in
              real time over WS /ws/alerts.
            </p>
            <span className="mt-4 inline-block font-display text-xs uppercase tracking-[0.16em] text-amber">
              View alerts →
            </span>
          </TerminalPanel>
        </Link>
      </motion.div>

      <motion.div variants={item}>
        <TerminalPanel title="Active Streams" windowId="LIVE-OPS">
          {streams.length === 0 ? (
            <p className="font-mono text-xs text-dim">No cameras are currently streaming.</p>
          ) : (
            <table className="w-full border-collapse font-mono text-xs">
              <thead>
                <tr className="border-b border-line text-left text-dim">
                  <th className="pb-2 font-normal uppercase tracking-wider">Camera</th>
                  <th className="pb-2 font-normal uppercase tracking-wider">Started</th>
                  <th className="pb-2 font-normal uppercase tracking-wider">Frames</th>
                  <th className="pb-2 font-normal uppercase tracking-wider">Status</th>
                </tr>
              </thead>
              <tbody>
                {streams.map((s) => (
                  <tr key={s.camera_id} className="border-b border-line/50 text-bone">
                    <td className="py-2 pr-4">
                      <Link href={`/cameras/${s.camera_id}`} className="text-amber hover:underline">
                        {s.camera_id}
                      </Link>
                    </td>
                    <td className="py-2 pr-4 text-dim">{formatTimestamp(s.started_at)}</td>
                    <td className="py-2 pr-4">{s.frames_processed}</td>
                    <td className="py-2">
                      <span className={s.last_error ? "text-alert" : "text-amber"}>
                        {s.last_error ? "ERROR" : "STREAMING"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </TerminalPanel>
      </motion.div>

      <motion.div variants={item}>
        <TerminalPanel title="Recent Events" windowId="LOG-EVENTS">
          {events.length === 0 ? (
            <p className="font-mono text-xs text-dim">No events raised yet.</p>
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
                {events.map((e, i) => (
                  <tr key={i} className="border-b border-line/50 text-bone">
                    <td className="py-2 pr-4">{e.type}</td>
                    <td className="py-2 pr-4">
                      <span
                        className={
                          e.severity === "critical"
                            ? "text-alert"
                            : e.severity === "warning"
                              ? "text-amber"
                              : "text-dim"
                        }
                      >
                        {e.severity.toUpperCase()}
                      </span>
                    </td>
                    <td className="py-2 pr-4 text-dim">{e.message}</td>
                    <td className="py-2 text-dim">{formatTimestamp(e.timestamp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="mt-4">
            <Link href="/events">
              <span className="font-display text-xs uppercase tracking-[0.16em] text-amber">
                View all events →
              </span>
            </Link>
          </div>
        </TerminalPanel>
      </motion.div>
    </motion.div>
  );
}

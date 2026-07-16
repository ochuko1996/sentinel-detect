"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { api, ApiError } from "@/lib/api";
import type { DetectImageResponse, DetectVideoResponse } from "@/lib/types";
import { formatTimestamp, pct } from "@/lib/utils";
import { DecodeText } from "@/components/ui/DecodeText";
import { TerminalPanel } from "@/components/ui/TerminalPanel";
import { Button } from "@/components/ui/Button";
import { Dropzone } from "@/components/detect/Dropzone";
import { BoundingBoxOverlay } from "@/components/detect/BoundingBoxOverlay";
import { ScanSweep } from "@/components/detect/ScanSweep";

type Mode = "image" | "video";

export default function DetectPage() {
  const [mode, setMode] = useState<Mode>("image");

  return (
    <div className="max-w-4xl space-y-8">
      <div>
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-amber">
          One-Shot Analysis
        </p>
        <h1 className="font-display text-4xl font-black uppercase tracking-tight text-bone sm:text-5xl">
          <DecodeText text="Detect" />
        </h1>
        <p className="mt-2 max-w-2xl font-mono text-sm text-dim">
          Run the detection pipeline (image) or the full detection → tracking →
          event → alert → storage pipeline (video) against an uploaded file —
          the same one-shot path a live camera stream runs continuously.
        </p>
      </div>

      <div className="flex gap-2 border-b border-line">
        {(["image", "video"] as Mode[]).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`border-b-2 px-4 py-2 font-display text-xs uppercase tracking-[0.16em] transition-colors ${
              mode === m ? "border-amber text-amber" : "border-transparent text-dim hover:text-bone"
            }`}
          >
            {m}
          </button>
        ))}
      </div>

      {mode === "image" ? <ImageDetect /> : <VideoDetect />}
    </div>
  );
}

function ImageDetect() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [result, setResult] = useState<DetectImageResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  async function handleFile(nextFile: File) {
    setFile(nextFile);
    setPreviewUrl(URL.createObjectURL(nextFile));
    setResult(null);
    setError(null);
    setRunning(true);
    try {
      const response = await api.detectImage(nextFile);
      setResult(response);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Detection failed.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <TerminalPanel title="Input Frame" windowId="IMG-IN">
        {previewUrl ? (
          <div className="relative">
            <BoundingBoxOverlay
              imageUrl={previewUrl}
              boxes={(result?.detections ?? []).map((d) => ({
                bbox: d.bbox,
                label: d.label,
                confidence: d.confidence,
              }))}
              activeIndex={activeIndex}
              onSelect={setActiveIndex}
            />
            {running && <ScanSweep />}
          </div>
        ) : (
          <Dropzone onFile={handleFile} />
        )}
        {file && (
          <button
            onClick={() => {
              setFile(null);
              setPreviewUrl(null);
              setResult(null);
              setError(null);
            }}
            className="mt-3 font-mono text-[11px] uppercase tracking-wider text-dim hover:text-amber"
          >
            ← Analyze a different frame
          </button>
        )}
      </TerminalPanel>

      <TerminalPanel title="Detections" windowId="IMG-OUT">
        {error && (
          <p className="border border-alert/60 bg-alert/10 px-3 py-2 font-mono text-xs text-alert">
            {error}
          </p>
        )}
        {running && <p className="font-mono text-xs text-dim">Analyzing frame...</p>}
        {!running && !result && !error && (
          <p className="font-mono text-xs text-dim">Upload an image to begin.</p>
        )}
        {result && (
          <div className="space-y-3">
            <p className="font-mono text-xs text-dim">
              {result.detections.length} object(s) detected ·{" "}
              {result.frame_width}×{result.frame_height} · active detectors:{" "}
              {result.active_detectors.join(", ") || "none"}
            </p>
            <ul className="space-y-2">
              {result.detections.map((detection, index) => (
                <motion.li
                  key={detection.id}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.05 }}
                  onClick={() => setActiveIndex(index)}
                  className={`flex cursor-pointer items-center justify-between border px-3 py-2 font-mono text-xs transition-colors ${
                    activeIndex === index ? "border-amber bg-amber/5" : "border-line"
                  }`}
                >
                  <span className="uppercase text-bone">{detection.label}</span>
                  <span className="text-dim">{pct(detection.confidence, 0)}</span>
                </motion.li>
              ))}
            </ul>
          </div>
        )}
      </TerminalPanel>
    </div>
  );
}

function VideoDetect() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<DetectVideoResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  async function handleFile(nextFile: File) {
    setFile(nextFile);
    setResult(null);
    setError(null);
    setRunning(true);
    try {
      const response = await api.detectVideo(nextFile);
      setResult(response);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Detection failed.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-4">
      <TerminalPanel title="Video Upload" windowId="VID-IN">
        <Dropzone
          onFile={handleFile}
          accept="video/mp4,video/avi,video/quicktime,video/x-matroska"
          label="DROP VIDEO OR CLICK TO BROWSE"
          hint="MP4 / AVI / MOV / MKV — up to 2000 frames processed"
        />
        {file && (
          <p className="mt-3 font-mono text-[11px] text-dim">
            {file.name} ({(file.size / 1024 / 1024).toFixed(1)} MB)
          </p>
        )}
      </TerminalPanel>

      {error && (
        <div className="border border-alert/60 bg-alert/10 px-4 py-3 font-mono text-xs text-alert">
          {error}
        </div>
      )}
      {running && (
        <div className="border border-line-bright px-4 py-3 font-mono text-xs text-dim">
          Processing video — decoding frames, running detection, tracking, and
          the rule engine. This can take a while for longer clips.
        </div>
      )}

      {result && (
        <div className="grid gap-4 lg:grid-cols-2">
          <TerminalPanel title="Run Summary" windowId="VID-SUM">
            <dl className="grid grid-cols-2 gap-3 font-mono text-xs">
              <SummaryStat label="Frames Processed" value={String(result.frames_processed)} />
              <SummaryStat label="Tracks" value={String(result.tracks.length)} />
              <SummaryStat label="Events" value={String(result.events.length)} />
              <SummaryStat label="Detections Stored" value={String(result.detections_stored)} />
              <SummaryStat label="Events Stored" value={String(result.events_stored)} />
              <SummaryStat label="Alerts Stored" value={String(result.alerts_stored)} />
            </dl>
            <p className="mt-3 font-mono text-[10px] text-dim">
              Active detectors: {result.active_detectors.join(", ") || "none"}
              <br />
              Active rules: {result.active_rules.join(", ") || "none"}
            </p>
          </TerminalPanel>

          <TerminalPanel title="Tracked Objects" windowId="VID-TRACKS">
            {result.tracks.length === 0 ? (
              <p className="font-mono text-xs text-dim">No objects tracked in this clip.</p>
            ) : (
              <table className="w-full border-collapse font-mono text-xs">
                <thead>
                  <tr className="border-b border-line text-left text-dim">
                    <th className="pb-2 font-normal uppercase tracking-wider">Track</th>
                    <th className="pb-2 font-normal uppercase tracking-wider">Label</th>
                    <th className="pb-2 font-normal uppercase tracking-wider">Frames</th>
                    <th className="pb-2 font-normal uppercase tracking-wider">Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {result.tracks.map((track) => (
                    <tr key={track.track_id} className="border-b border-line/50 text-bone">
                      <td className="py-2 pr-4">#{track.track_id}</td>
                      <td className="py-2 pr-4 uppercase">{track.label}</td>
                      <td className="py-2 pr-4">{track.frames_tracked}</td>
                      <td className="py-2">{pct(track.last_confidence, 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </TerminalPanel>

          <TerminalPanel title="Events Raised" windowId="VID-EVENTS" className="lg:col-span-2">
            {result.events.length === 0 ? (
              <p className="font-mono text-xs text-dim">No events raised during this clip.</p>
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
                  {result.events.map((event, i) => (
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
                      <td className="py-2 pr-4 text-dim">{event.message}</td>
                      <td className="py-2 text-dim">{formatTimestamp(event.timestamp)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </TerminalPanel>
        </div>
      )}

      {!file && !running && !result && (
        <Button variant="ghost" disabled>
          Upload a video above to begin
        </Button>
      )}
    </div>
  );
}

function SummaryStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="uppercase tracking-[0.2em] text-dim">{label}</dt>
      <dd className="mt-1 text-lg font-semibold text-bone">{value}</dd>
    </div>
  );
}

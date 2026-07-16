"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { SourceType } from "@/lib/types";
import { DecodeText } from "@/components/ui/DecodeText";
import { TerminalPanel } from "@/components/ui/TerminalPanel";
import { Button } from "@/components/ui/Button";

const SOURCE_TYPES: SourceType[] = [
  "rtsp",
  "webcam",
  "usb",
  "ip_camera",
  "video_file",
  "directory",
  "image",
];

const DETECTOR_KEYS = ["person", "vehicle", "weapon", "fire", "smoke", "ppe", "animal"];

export default function NewCameraPage() {
  const router = useRouter();
  const [id, setId] = useState("");
  const [name, setName] = useState("");
  const [sourceType, setSourceType] = useState<SourceType>("rtsp");
  const [uri, setUri] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [detectors, setDetectors] = useState<Set<string>>(new Set(["person"]));
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function toggleDetector(key: string) {
    setDetectors((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const camera = await api.createCamera({
        id,
        name,
        source_type: sourceType,
        uri,
        enabled,
        enabled_detectors: Array.from(detectors),
      });
      router.push(`/cameras/${camera.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to create camera.");
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-2xl space-y-8">
      <div>
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-amber">
          Input Sources
        </p>
        <h1 className="font-display text-4xl font-black uppercase tracking-tight text-bone sm:text-5xl">
          <DecodeText text="Register Camera" />
        </h1>
      </div>

      <TerminalPanel title="Camera Configuration" windowId="CAM-NEW">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Camera ID">
              <input
                value={id}
                onChange={(e) => setId(e.target.value)}
                placeholder="cam-front-door"
                className="w-full border border-line bg-panel-raised px-3 py-2 font-mono text-sm text-bone outline-none focus:border-amber"
                required
              />
            </Field>
            <Field label="Display Name">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Front Door"
                className="w-full border border-line bg-panel-raised px-3 py-2 font-mono text-sm text-bone outline-none focus:border-amber"
                required
              />
            </Field>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Source Type">
              <select
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value as SourceType)}
                className="w-full border border-line bg-panel-raised px-3 py-2 font-mono text-sm text-bone outline-none focus:border-amber"
              >
                {SOURCE_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t.toUpperCase()}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="URI / Device / Path">
              <input
                value={uri}
                onChange={(e) => setUri(e.target.value)}
                placeholder="rtsp://192.168.1.20/stream1"
                className="w-full border border-line bg-panel-raised px-3 py-2 font-mono text-sm text-bone outline-none focus:border-amber"
                required
              />
            </Field>
          </div>

          <Field label="Active Detectors">
            <div className="flex flex-wrap gap-2">
              {DETECTOR_KEYS.map((key) => {
                const active = detectors.has(key);
                return (
                  <button
                    type="button"
                    key={key}
                    onClick={() => toggleDetector(key)}
                    className={`border px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider transition-colors ${
                      active
                        ? "border-amber bg-amber/10 text-amber"
                        : "border-line text-dim hover:border-line-bright"
                    }`}
                  >
                    {key}
                  </button>
                );
              })}
            </div>
          </Field>

          <label className="flex items-center gap-2 font-mono text-xs text-bone">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              className="accent-amber"
            />
            Enabled
          </label>

          {error && (
            <p className="border border-alert/60 bg-alert/10 px-3 py-2 font-mono text-xs text-alert">
              {error}
            </p>
          )}

          <div className="flex gap-3">
            <Button type="submit" disabled={submitting}>
              {submitting ? "Registering..." : "Register Camera"}
            </Button>
            <Button type="button" variant="ghost" onClick={() => router.push("/cameras")}>
              Cancel
            </Button>
          </div>
        </form>
      </TerminalPanel>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block font-mono text-[10px] uppercase tracking-[0.2em] text-dim">
        {label}
      </label>
      {children}
    </div>
  );
}

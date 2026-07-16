"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { Camera, StreamStatusResponse } from "@/lib/types";
import { roleAtLeast } from "@/lib/utils";
import { DecodeText } from "@/components/ui/DecodeText";
import { TerminalPanel } from "@/components/ui/TerminalPanel";
import { Button } from "@/components/ui/Button";
import { StatusDot } from "@/components/ui/StatusDot";

export default function CameraDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { identity } = useAuth();
  const [camera, setCamera] = useState<Camera | null>(null);
  const [stream, setStream] = useState<StreamStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const canOperate = roleAtLeast(identity?.role ?? null, "operator");
  const canDelete = roleAtLeast(identity?.role ?? null, "admin");

  async function load() {
    try {
      const [c, streams] = await Promise.all([api.getCamera(params.id), api.listStreams()]);
      setCamera(c);
      setStream(streams.find((s) => s.camera_id === params.id) ?? null);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load camera.");
    }
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  async function handleStart() {
    setBusy(true);
    setActionError(null);
    try {
      await api.startStream(params.id);
      await load();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.detail : "Failed to start stream.");
    } finally {
      setBusy(false);
    }
  }

  async function handleStop() {
    setBusy(true);
    setActionError(null);
    try {
      await api.stopStream(params.id);
      await load();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.detail : "Failed to stop stream.");
    } finally {
      setBusy(false);
    }
  }

  async function handleToggleEnabled() {
    if (!camera) return;
    setBusy(true);
    setActionError(null);
    try {
      await api.updateCamera(camera.id, { enabled: !camera.enabled });
      await load();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.detail : "Failed to update camera.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!camera) return;
    if (!confirm(`Delete camera "${camera.id}"? This cannot be undone.`)) return;
    setBusy(true);
    setActionError(null);
    try {
      await api.deleteCamera(camera.id);
      router.push("/cameras");
    } catch (err) {
      setActionError(err instanceof ApiError ? err.detail : "Failed to delete camera.");
      setBusy(false);
    }
  }

  if (error) {
    return (
      <div className="border border-alert/60 bg-alert/10 px-4 py-3 font-mono text-xs text-alert">
        {error}
      </div>
    );
  }

  if (!camera) {
    return <p className="font-mono text-xs text-dim">Loading...</p>;
  }

  const streaming = stream !== null;

  return (
    <div className="max-w-3xl space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.3em] text-amber">
            Camera Detail
          </p>
          <h1 className="font-display text-4xl font-black uppercase tracking-tight text-bone sm:text-5xl">
            <DecodeText text={camera.name} />
          </h1>
          <p className="mt-1 font-mono text-xs text-dim">{camera.id}</p>
        </div>
        <div className="flex items-center gap-2 border border-line px-3 py-1.5">
          <StatusDot tone={streaming ? "online" : "offline"} pulse={streaming} />
          <span className="font-mono text-[10px] uppercase tracking-wider text-dim">
            {streaming ? "LIVE" : "STOPPED"}
          </span>
        </div>
      </div>

      {actionError && (
        <div className="border border-alert/60 bg-alert/10 px-4 py-3 font-mono text-xs text-alert">
          {actionError}
        </div>
      )}

      <TerminalPanel title="Configuration" windowId="CAM-CFG">
        <dl className="grid grid-cols-2 gap-4 font-mono text-xs sm:grid-cols-3">
          <Detail label="Source Type" value={camera.source_type.toUpperCase()} />
          <Detail label="URI" value={camera.uri} className="col-span-2 sm:col-span-2" />
          <Detail label="Enabled" value={camera.enabled ? "YES" : "NO"} />
          <Detail
            label="Frame Rate Limit"
            value={camera.frame_rate_limit ? `${camera.frame_rate_limit} fps` : "Unlimited"}
          />
          <Detail label="Regions" value={String(camera.regions.length)} />
          <Detail
            label="Detectors"
            value={camera.enabled_detectors.length ? camera.enabled_detectors.join(", ") : "None"}
            className="col-span-2 sm:col-span-3"
          />
        </dl>

        {canOperate && (
          <div className="mt-6 flex flex-wrap gap-3 border-t border-line pt-4">
            {streaming ? (
              <Button variant="danger" onClick={handleStop} disabled={busy}>
                Stop Stream
              </Button>
            ) : (
              <Button onClick={handleStart} disabled={busy || !camera.enabled}>
                Start Stream
              </Button>
            )}
            <Link href={`/cameras/${camera.id}/live`}>
              <Button variant="ghost" disabled={!streaming}>
                Open Live Telemetry
              </Button>
            </Link>
            <Button variant="ghost" onClick={handleToggleEnabled} disabled={busy}>
              {camera.enabled ? "Disable Camera" : "Enable Camera"}
            </Button>
            {canDelete && (
              <Button variant="danger" onClick={handleDelete} disabled={busy}>
                Delete Camera
              </Button>
            )}
          </div>
        )}
      </TerminalPanel>
    </div>
  );
}

function Detail({
  label,
  value,
  className,
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div className={className}>
      <dt className="uppercase tracking-[0.2em] text-dim">{label}</dt>
      <dd className="mt-1 break-all text-bone">{value}</dd>
    </div>
  );
}

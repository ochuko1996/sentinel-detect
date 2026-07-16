"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { Camera, StreamStatusResponse } from "@/lib/types";
import { roleAtLeast } from "@/lib/utils";
import { DecodeText } from "@/components/ui/DecodeText";
import { TerminalPanel } from "@/components/ui/TerminalPanel";
import { Button } from "@/components/ui/Button";
import { StatusDot } from "@/components/ui/StatusDot";

export default function CamerasPage() {
  const { identity } = useAuth();
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [streams, setStreams] = useState<StreamStatusResponse[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const [c, s] = await Promise.all([api.listCameras(), api.listStreams()]);
      setCameras(c);
      setStreams(s);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load cameras.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 8000);
    return () => clearInterval(interval);
  }, []);

  const streamingIds = new Set(streams.map((s) => s.camera_id));
  const canManage = roleAtLeast(identity?.role ?? null, "operator");

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.3em] text-amber">
            Input Sources
          </p>
          <h1 className="font-display text-4xl font-black uppercase tracking-tight text-bone sm:text-5xl">
            <DecodeText text="Cameras" />
          </h1>
        </div>
        {canManage && (
          <Link href="/cameras/new">
            <Button>Register Camera</Button>
          </Link>
        )}
      </div>

      {error && (
        <div className="border border-alert/60 bg-alert/10 px-4 py-3 font-mono text-xs text-alert">
          {error}
        </div>
      )}

      <TerminalPanel title="Registered Cameras" windowId="CAM-INDEX">
        {loading ? (
          <p className="font-mono text-xs text-dim">Loading...</p>
        ) : cameras.length === 0 ? (
          <p className="font-mono text-xs text-dim">
            No cameras registered yet.{" "}
            {canManage && (
              <Link href="/cameras/new" className="text-amber hover:underline">
                Register one
              </Link>
            )}
          </p>
        ) : (
          <table className="w-full border-collapse font-mono text-xs">
            <thead>
              <tr className="border-b border-line text-left text-dim">
                <th className="pb-2 font-normal uppercase tracking-wider">ID</th>
                <th className="pb-2 font-normal uppercase tracking-wider">Name</th>
                <th className="pb-2 font-normal uppercase tracking-wider">Source</th>
                <th className="pb-2 font-normal uppercase tracking-wider">Enabled</th>
                <th className="pb-2 font-normal uppercase tracking-wider">Stream</th>
              </tr>
            </thead>
            <tbody>
              {cameras.map((camera, i) => {
                const streaming = streamingIds.has(camera.id);
                return (
                  <motion.tr
                    key={camera.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.03 }}
                    className="border-b border-line/50 text-bone"
                  >
                    <td className="py-2 pr-4">
                      <Link href={`/cameras/${camera.id}`} className="text-amber hover:underline">
                        {camera.id}
                      </Link>
                    </td>
                    <td className="py-2 pr-4">{camera.name}</td>
                    <td className="py-2 pr-4 uppercase text-dim">{camera.source_type}</td>
                    <td className="py-2 pr-4">
                      <span className={camera.enabled ? "text-amber" : "text-dim"}>
                        {camera.enabled ? "ENABLED" : "DISABLED"}
                      </span>
                    </td>
                    <td className="py-2">
                      <div className="flex items-center gap-2">
                        <StatusDot tone={streaming ? "online" : "offline"} pulse={streaming} />
                        <span className="text-dim">{streaming ? "LIVE" : "STOPPED"}</span>
                      </div>
                    </td>
                  </motion.tr>
                );
              })}
            </tbody>
          </table>
        )}
      </TerminalPanel>
    </div>
  );
}

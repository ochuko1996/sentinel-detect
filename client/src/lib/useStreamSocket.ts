"use client";

import { useEffect, useRef, useState } from "react";
import { wsUrl } from "./api";
import type { StreamFrameMessage } from "./types";

export type SocketStatus = "connecting" | "open" | "closed";

/** Subscribes to WS /ws/stream/{camera_id} — carries only per-frame track
 * telemetry (bbox/label/confidence), never the frame's actual pixels; see
 * components/stream/TrackRadar.tsx for why the live view is a schematic
 * plot, not a video overlay. */
export function useStreamSocket(cameraId: string, enabled: boolean) {
  const [latest, setLatest] = useState<StreamFrameMessage | null>(null);
  const [status, setStatus] = useState<SocketStatus>("closed");
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!enabled) {
      setStatus("closed");
      return;
    }

    setStatus("connecting");
    const ws = new WebSocket(wsUrl(`/ws/stream/${cameraId}`));
    wsRef.current = ws;

    ws.onopen = () => setStatus("open");
    ws.onclose = () => setStatus("closed");
    ws.onerror = () => setStatus("closed");
    ws.onmessage = (event) => {
      try {
        setLatest(JSON.parse(event.data) as StreamFrameMessage);
      } catch {
        // malformed frame — skip it, keep the connection alive
      }
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [cameraId, enabled]);

  return { latest, status };
}

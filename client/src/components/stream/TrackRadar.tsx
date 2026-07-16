"use client";

import { motion } from "framer-motion";
import type { StreamFrameMessage } from "@/lib/types";
import { pct } from "@/lib/utils";

const CRITICAL_LABELS = new Set(["gun", "rifle", "knife", "fire", "flame", "smoke"]);

/**
 * A schematic plot of the current frame's tracked objects, auto-scaled to
 * the observed bounding-box extent — not a video overlay. `WS
 * /ws/stream/{camera_id}` only ever carries track telemetry (bbox/label/
 * confidence), never the frame's actual pixels or its real width/height,
 * so there is no honest way to position boxes against a real image here.
 * (See lib/useStreamSocket.ts.)
 */
export function TrackRadar({ message }: { message: StreamFrameMessage | null }) {
  if (!message || message.tracks.length === 0) {
    return (
      <div className="flex aspect-video items-center justify-center border border-line-bright bg-black/40">
        <p className="font-mono text-xs text-dim">NO TRACKED OBJECTS IN CURRENT FRAME</p>
      </div>
    );
  }

  const xs = message.tracks.flatMap((t) => [t.bbox.x1, t.bbox.x2]);
  const ys = message.tracks.flatMap((t) => [t.bbox.y1, t.bbox.y2]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const spanX = Math.max(maxX - minX, 1);
  const spanY = Math.max(maxY - minY, 1);
  // Pad so boxes never touch the plot's edge exactly.
  const pad = 0.08;

  return (
    <div className="relative aspect-video overflow-hidden border border-line-bright bg-black/40 bg-grid-fine bg-[length:20px_20px]">
      {message.tracks.map((track) => {
        const left = pad + ((track.bbox.x1 - minX) / spanX) * (1 - 2 * pad);
        const top = pad + ((track.bbox.y1 - minY) / spanY) * (1 - 2 * pad);
        const width = ((track.bbox.x2 - track.bbox.x1) / spanX) * (1 - 2 * pad);
        const height = ((track.bbox.y2 - track.bbox.y1) / spanY) * (1 - 2 * pad);
        const critical = CRITICAL_LABELS.has(track.label);
        const colorClass = critical ? "border-alert" : "border-amber";

        return (
          <motion.div
            key={track.track_id}
            layout
            transition={{ duration: 0.25, ease: "easeOut" }}
            className={`absolute border-2 ${colorClass}`}
            style={{
              left: `${left * 100}%`,
              top: `${top * 100}%`,
              width: `${Math.max(width * 100, 3)}%`,
              height: `${Math.max(height * 100, 3)}%`,
            }}
          >
            <span
              className={`absolute -top-5 left-0 whitespace-nowrap px-1 py-0.5 font-mono text-[9px] uppercase tracking-wider ${
                critical ? "bg-alert text-void" : "bg-amber text-void"
              }`}
            >
              #{track.track_id} {track.label} · {pct(track.confidence, 0)}
            </span>
          </motion.div>
        );
      })}
    </div>
  );
}

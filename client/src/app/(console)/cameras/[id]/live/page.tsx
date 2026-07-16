"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useStreamSocket } from "@/lib/useStreamSocket";
import { formatTimestamp, pct } from "@/lib/utils";
import { DecodeText } from "@/components/ui/DecodeText";
import { TerminalPanel } from "@/components/ui/TerminalPanel";
import { StatusDot } from "@/components/ui/StatusDot";
import { TrackRadar } from "@/components/stream/TrackRadar";

export default function LiveStreamPage() {
  const params = useParams<{ id: string }>();
  const { latest, status } = useStreamSocket(params.id, true);

  const tone = status === "open" ? "online" : status === "connecting" ? "degraded" : "offline";

  return (
    <div className="max-w-4xl space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.3em] text-amber">
            Live Telemetry
          </p>
          <h1 className="font-display text-4xl font-black uppercase tracking-tight text-bone sm:text-5xl">
            <DecodeText text={params.id} />
          </h1>
          <Link href={`/cameras/${params.id}`} className="font-mono text-xs text-dim hover:text-amber">
            ← Back to camera detail
          </Link>
        </div>
        <div className="flex items-center gap-2 border border-line px-3 py-1.5">
          <StatusDot tone={tone} />
          <span className="font-mono text-[10px] uppercase tracking-wider text-dim">
            WS {status.toUpperCase()}
          </span>
        </div>
      </div>

      <TerminalPanel title="Schematic Track Plot" windowId="RADAR">
        <p className="mb-3 font-mono text-[10px] text-dim">
          Auto-scaled to the current frame&apos;s tracked-object extent — this is
          telemetry, not the camera&apos;s actual video. `WS /ws/stream/&#123;camera_id&#125;`
          carries only bounding-box/label/confidence per track, never frame
          pixels, so there is no real image to overlay boxes on here.
        </p>
        <TrackRadar message={latest} />
        {latest && (
          <p className="mt-3 font-mono text-[10px] text-dim">
            Frame #{latest.frame_index} · {formatTimestamp(latest.timestamp)}
          </p>
        )}
      </TerminalPanel>

      <TerminalPanel title="Tracked Objects (Current Frame)" windowId="TRACK-LOG">
        {!latest || latest.tracks.length === 0 ? (
          <p className="font-mono text-xs text-dim">No tracked objects right now.</p>
        ) : (
          <table className="w-full border-collapse font-mono text-xs">
            <thead>
              <tr className="border-b border-line text-left text-dim">
                <th className="pb-2 font-normal uppercase tracking-wider">Track</th>
                <th className="pb-2 font-normal uppercase tracking-wider">Label</th>
                <th className="pb-2 font-normal uppercase tracking-wider">Confidence</th>
                <th className="pb-2 font-normal uppercase tracking-wider">BBox (x1,y1,x2,y2)</th>
              </tr>
            </thead>
            <tbody>
              {latest.tracks.map((track) => (
                <tr key={track.track_id} className="border-b border-line/50 text-bone">
                  <td className="py-2 pr-4">#{track.track_id}</td>
                  <td className="py-2 pr-4 uppercase">{track.label}</td>
                  <td className="py-2 pr-4">{pct(track.confidence, 0)}</td>
                  <td className="py-2 text-dim">
                    {[track.bbox.x1, track.bbox.y1, track.bbox.x2, track.bbox.y2]
                      .map((n) => n.toFixed(0))
                      .join(", ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </TerminalPanel>
    </div>
  );
}

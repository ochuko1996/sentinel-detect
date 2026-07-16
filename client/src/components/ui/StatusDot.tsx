import { cn } from "@/lib/utils";

type Tone = "online" | "degraded" | "offline";

const TONE_COLOR: Record<Tone, string> = {
  online: "bg-amber",
  degraded: "bg-alert-dim",
  offline: "bg-alert",
};

export function StatusDot({ tone, pulse = true }: { tone: Tone; pulse?: boolean }) {
  return (
    <span className="relative inline-flex h-2.5 w-2.5">
      {pulse && tone !== "offline" && (
        <span
          className={cn(
            "absolute inline-flex h-full w-full animate-pulse-ring rounded-full",
            TONE_COLOR[tone],
          )}
        />
      )}
      <span
        className={cn("relative inline-flex h-2.5 w-2.5 rounded-full", TONE_COLOR[tone])}
      />
    </span>
  );
}

import { useId, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export function TerminalPanel({
  title,
  windowId,
  children,
  className,
  bodyClassName,
  accent = "amber",
  fillHeight = false,
}: {
  title: string;
  windowId?: string;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  accent?: "amber" | "alert";
  /** When true, the panel takes the full height of its flex/grid parent
   * and the body scrolls internally instead of growing the page — used
   * on screens (e.g. live stream view) that should fit within the
   * viewport rather than pushing it taller. */
  fillHeight?: boolean;
}) {
  const reactId = useId();
  const id = windowId ?? `WIN-0x${hashToHex(reactId)}`;
  const accentClass = accent === "amber" ? "border-amber/40" : "border-alert/50";

  return (
    <div
      className={cn(
        "relative border bg-panel/80 backdrop-blur-sm",
        accentClass,
        fillHeight && "flex h-full flex-col",
        className,
      )}
    >
      {/* corner brackets */}
      <span className="pointer-events-none absolute -left-px -top-px h-3 w-3 border-l-2 border-t-2 border-amber" />
      <span className="pointer-events-none absolute -right-px -top-px h-3 w-3 border-r-2 border-t-2 border-amber" />
      <span className="pointer-events-none absolute -bottom-px -left-px h-3 w-3 border-b-2 border-l-2 border-amber" />
      <span className="pointer-events-none absolute -bottom-px -right-px h-3 w-3 border-b-2 border-r-2 border-amber" />

      <div className="flex shrink-0 items-center justify-between border-b border-line px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="h-1.5 w-1.5 bg-amber" />
          <h3 className="font-display text-sm uppercase tracking-[0.18em] text-bone">
            {title}
          </h3>
        </div>
        <span className="font-mono text-[10px] tracking-wider text-dim">{id}</span>
      </div>
      <div
        className={cn(
          "p-4",
          fillHeight && "min-h-0 flex-1 overflow-y-auto",
          bodyClassName,
        )}
      >
        {children}
      </div>
    </div>
  );
}

/** Deterministically turns React's opaque `useId()` string into a short
 * hex string for the fake "window id" — cosmetic only, not a real hash. */
function hashToHex(input: string): string {
  let hash = 0;
  for (let i = 0; i < input.length; i += 1) {
    hash = (hash * 31 + input.charCodeAt(i)) >>> 0;
  }
  return (hash % 0xffff).toString(16).toUpperCase().padStart(4, "0");
}

"use client";

import { useCallback, useRef, useState, type DragEvent } from "react";
import { cn } from "@/lib/utils";

export function Dropzone({
  onFile,
  accept = "image/jpeg,image/png,image/webp",
  label = "DROP IMAGE OR CLICK TO BROWSE",
  hint = "JPG / PNG / WEBP — single frame",
  compact = false,
}: {
  onFile: (file: File) => void;
  accept?: string;
  label?: string;
  hint?: string;
  compact?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const handleDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setDragging(false);
      const file = event.dataTransfer.files?.[0];
      if (file) onFile(file);
    },
    [onFile],
  );

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center gap-2 border border-dashed text-center transition-colors",
        compact ? "p-6" : "p-14",
        dragging ? "border-amber bg-amber/5" : "border-line-bright hover:border-amber/60",
      )}
    >
      <svg viewBox="0 0 24 24" className="h-8 w-8 text-dim" fill="none">
        <rect x="3" y="3" width="18" height="18" rx="1" stroke="currentColor" strokeWidth="1.3" />
        <path d="M3 16l5-5 4 4 3-3 6 6" stroke="currentColor" strokeWidth="1.3" />
        <circle cx="8.5" cy="8.5" r="1.5" stroke="currentColor" strokeWidth="1.3" />
      </svg>
      <p className="font-display text-xs uppercase tracking-[0.16em] text-bone">{label}</p>
      <p className="font-mono text-[10px] text-dim">{hint}</p>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onFile(file);
          event.target.value = "";
        }}
      />
    </div>
  );
}

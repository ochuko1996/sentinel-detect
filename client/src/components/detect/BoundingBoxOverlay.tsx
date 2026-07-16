"use client";

import { useState, type SyntheticEvent } from "react";
import { motion } from "framer-motion";
import type { BoundingBox, DetectionClass } from "@/lib/types";
import { pct } from "@/lib/utils";

const CRITICAL_CLASSES: ReadonlySet<DetectionClass> = new Set([
  "gun",
  "rifle",
  "knife",
  "fire",
  "flame",
  "smoke",
]);

export interface OverlayBox {
  bbox: BoundingBox;
  label: string;
  confidence: number;
}

export function BoundingBoxOverlay({
  imageUrl,
  boxes,
  activeIndex,
  onSelect,
}: {
  imageUrl: string;
  boxes: OverlayBox[];
  activeIndex?: number | null;
  onSelect?: (index: number) => void;
}) {
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null);

  function handleLoad(event: SyntheticEvent<HTMLImageElement>) {
    const img = event.currentTarget;
    setNatural({ w: img.naturalWidth, h: img.naturalHeight });
  }

  return (
    <div className="relative border border-line bg-black">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={imageUrl}
        alt="Analyzed frame"
        onLoad={handleLoad}
        className="block h-auto w-full select-none"
        draggable={false}
      />
      {natural &&
        boxes.map((box, index) => {
          const { bbox } = box;
          const left = (bbox.x1 / natural.w) * 100;
          const top = (bbox.y1 / natural.h) * 100;
          const width = ((bbox.x2 - bbox.x1) / natural.w) * 100;
          const height = ((bbox.y2 - bbox.y1) / natural.h) * 100;
          const active = activeIndex === index;
          const critical = CRITICAL_CLASSES.has(box.label as DetectionClass);
          const colorClass = critical ? "border-alert" : "border-amber";

          return (
            <motion.button
              key={index}
              type="button"
              onClick={() => onSelect?.(index)}
              initial={{ opacity: 0, scale: 0.85 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: index * 0.08, duration: 0.3, ease: "easeOut" }}
              className={`absolute border-2 ${colorClass} ${active ? "z-10" : ""} ${onSelect ? "cursor-pointer" : "cursor-default"}`}
              style={{
                left: `${left}%`,
                top: `${top}%`,
                width: `${width}%`,
                height: `${height}%`,
                boxShadow: active
                  ? `0 0 0 3px ${critical ? "rgba(255,59,59,0.35)" : "rgba(255,176,0,0.35)"}`
                  : undefined,
              }}
            >
              {/* corner brackets, targeting-reticle style */}
              <span className={`absolute -left-[2px] -top-[2px] h-3 w-3 border-l-2 border-t-2 ${colorClass}`} />
              <span className={`absolute -right-[2px] -top-[2px] h-3 w-3 border-r-2 border-t-2 ${colorClass}`} />
              <span className={`absolute -bottom-[2px] -left-[2px] h-3 w-3 border-b-2 border-l-2 ${colorClass}`} />
              <span className={`absolute -bottom-[2px] -right-[2px] h-3 w-3 border-b-2 border-r-2 ${colorClass}`} />

              <span
                className={`absolute -top-6 left-0 whitespace-nowrap px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider ${
                  critical ? "bg-alert text-void" : "bg-amber text-void"
                }`}
              >
                {box.label} · {pct(box.confidence, 0)}
              </span>
            </motion.button>
          );
        })}
    </div>
  );
}

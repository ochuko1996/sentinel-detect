"use client";

import { motion } from "framer-motion";
import { pct } from "@/lib/utils";

export function ConfidenceGauge({
  value,
  label,
  size = 96,
  tone = "amber",
}: {
  value: number;
  label: string;
  size?: number;
  tone?: "amber" | "alert";
}) {
  const stroke = 6;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(1, value));
  const color = tone === "amber" ? "#ffb000" : "#ff3b3b";

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke="rgba(178,196,178,0.15)"
            strokeWidth={stroke}
            fill="none"
          />
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke={color}
            strokeWidth={stroke}
            fill="none"
            strokeLinecap="square"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: circumference * (1 - clamped) }}
            transition={{ duration: 1, ease: "easeOut" }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center font-mono text-lg font-semibold text-bone">
          {pct(clamped, 0)}
        </div>
      </div>
      <span className="font-display text-[11px] uppercase tracking-[0.18em] text-dim">
        {label}
      </span>
    </div>
  );
}

"use client";

import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type Variant = "primary" | "ghost" | "danger";

const VARIANT_CLASS: Record<Variant, string> = {
  primary:
    "bg-amber text-void border-amber hover:bg-amber-glow hover:border-amber-glow disabled:bg-dim disabled:border-dim",
  ghost:
    "bg-transparent text-bone border-line hover:border-amber hover:text-amber disabled:text-dim",
  danger:
    "bg-transparent text-alert border-alert/60 hover:bg-alert hover:text-void disabled:text-dim disabled:border-line",
};

export function Button({
  variant = "primary",
  className,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 border px-4 py-2 font-display text-xs uppercase tracking-[0.16em] transition-colors duration-150 disabled:cursor-not-allowed",
        VARIANT_CLASS[variant],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

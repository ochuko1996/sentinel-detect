"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const ITEMS = [
  { index: "01", label: "Dashboard", href: "/" },
  { index: "02", label: "Cameras", href: "/cameras" },
  { index: "03", label: "Detect", href: "/detect" },
  { index: "04", label: "Events", href: "/events" },
  { index: "05", label: "Alerts", href: "/alerts" },
  { index: "06", label: "Config", href: "/config" },
];

export function SideNav() {
  const pathname = usePathname();

  return (
    <nav className="flex w-56 shrink-0 flex-col overflow-y-auto border-r border-line bg-panel/60">
      <div className="border-b border-line px-4 py-3">
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-dim">Operations Menu</p>
      </div>
      <ul className="flex flex-1 flex-col py-2">
        {ITEMS.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                className={cn(
                  "group relative flex items-center gap-3 border-l-2 px-4 py-3 transition-colors duration-150",
                  active
                    ? "border-amber bg-amber/5 text-amber"
                    : "border-transparent text-dim hover:border-line-bright hover:text-bone",
                )}
              >
                <span className="font-mono text-[11px] tabular-nums">{item.index}</span>
                <span className="font-display text-sm uppercase tracking-[0.14em]">
                  {item.label}
                </span>
                {active && (
                  <span className="absolute right-3 h-1.5 w-1.5 animate-pulse bg-amber" />
                )}
              </Link>
            </li>
          );
        })}
      </ul>
      <div className="border-t border-line px-4 py-3">
        <p className="font-mono text-[9px] leading-relaxed text-dim">
          ALL QUERIES ARE LOGGED. UNAUTHORIZED ACCESS TO THIS TERMINAL IS PROHIBITED
          UNDER OPERATIONS DIRECTIVE 7.2.
        </p>
      </div>
    </nav>
  );
}

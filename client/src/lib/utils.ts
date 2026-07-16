import { clsx, type ClassValue } from "clsx";
import type { UserRole } from "./types";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

/** Formats a 0..1 confidence score as a percentage string. */
export function pct(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

/** Shortens a UUID into a stamped "case file" reference number. */
export function caseRef(id: string): string {
  return id.replace(/-/g, "").slice(0, 8).toUpperCase();
}

export function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  return date
    .toISOString()
    .replace("T", " ")
    .replace(/\.\d+Z$/, "Z");
}

export function formatClock(date: Date): string {
  return date.toISOString().slice(11, 19) + " UTC";
}

export function formatDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

const ROLE_RANK: Record<UserRole, number> = {
  viewer: 0,
  operator: 1,
  admin: 2,
};

/** Whether `role` meets or exceeds `min` in the VIEWER < OPERATOR < ADMIN
 * ranking the backend enforces server-side — used only to hide/show
 * actions the API would reject anyway; never a substitute for that check. */
export function roleAtLeast(role: UserRole | null, min: UserRole): boolean {
  if (!role) return false;
  return ROLE_RANK[role] >= ROLE_RANK[min];
}

"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

/** Redirects to /login if there's no stored session once the client has
 * finished checking localStorage (`ready`). Renders nothing meaningful
 * until then, to avoid a flash of gated content. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { identity, ready } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (ready && !identity) {
      router.replace("/login");
    }
  }, [ready, identity, router]);

  if (!ready || !identity) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-dim">
          Verifying session...
        </p>
      </div>
    );
  }

  return <>{children}</>;
}

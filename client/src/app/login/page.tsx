"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { TerminalPanel } from "@/components/ui/TerminalPanel";
import { Button } from "@/components/ui/Button";
import { DecodeText } from "@/components/ui/DecodeText";

export default function LoginPage() {
  const router = useRouter();
  const { identity, ready, setIdentity } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (ready && identity) router.replace("/");
  }, [ready, identity, router]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const token = await api.login(username, password);

      setIdentity({ username: token.username, role: token.role });
      router.push("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Login failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-1 items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <p className="font-mono text-xs uppercase tracking-[0.3em] text-amber">
            Access Control
          </p>
          <h1 className="font-display text-3xl font-black uppercase tracking-tight text-bone">
            <DecodeText text="SENTINEL Detect" />
          </h1>
        </div>

        <TerminalPanel title="Authenticate" windowId="AUTH-001">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="mb-1 block font-mono text-[10px] uppercase tracking-[0.2em] text-dim">
                Username
              </label>
              <input
                autoFocus
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                className="w-full border border-line bg-panel-raised px-3 py-2 font-mono text-sm text-bone outline-none focus:border-amber"
                autoComplete="username"
                required
              />
            </div>
            <div>
              <label className="mb-1 block font-mono text-[10px] uppercase tracking-[0.2em] text-dim">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="w-full border border-line bg-panel-raised px-3 py-2 font-mono text-sm text-bone outline-none focus:border-amber"
                autoComplete="current-password"
                required
              />
            </div>

            {error && (
              <p className="border border-alert/60 bg-alert/10 px-3 py-2 font-mono text-xs text-alert">
                {error}
              </p>
            )}

            <Button type="submit" disabled={submitting} className="w-full">
              {submitting ? "Authenticating..." : "Log In"}
            </Button>
          </form>
        </TerminalPanel>

        <p className="mt-4 text-center font-mono text-[10px] text-dim">
          All login attempts are logged. See the backend README for
          bootstrapping the first admin account.
        </p>
      </div>
    </div>
  );
}

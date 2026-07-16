"use client";

import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { ConfigurationEntry } from "@/lib/types";
import { formatTimestamp, roleAtLeast } from "@/lib/utils";
import { DecodeText } from "@/components/ui/DecodeText";
import { TerminalPanel } from "@/components/ui/TerminalPanel";
import { Button } from "@/components/ui/Button";

export default function ConfigPage() {
  const { identity } = useAuth();
  const [entries, setEntries] = useState<ConfigurationEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const canWrite = roleAtLeast(identity?.role ?? null, "admin");

  async function load() {
    setLoading(true);
    try {
      const result = await api.listConfig();
      setEntries(result);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load configuration.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    let parsed: unknown;
    try {
      parsed = JSON.parse(value);
    } catch {
      setFormError('Value must be valid JSON (e.g. "30", "true", "\\"text\\"", {"a":1}).');
      return;
    }
    setSubmitting(true);
    try {
      await api.upsertConfig(key, parsed as ConfigurationEntry["value"]);
      setKey("");
      setValue("");
      await load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.detail : "Failed to save entry.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-3xl space-y-8">
      <div>
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-amber">
          Runtime Settings
        </p>
        <h1 className="font-display text-4xl font-black uppercase tracking-tight text-bone sm:text-5xl">
          <DecodeText text="Configuration" />
        </h1>
        <p className="mt-2 max-w-2xl font-mono text-sm text-dim">
          Runtime key/value entries, distinct from the process-level
          environment configuration (which requires a restart). Writes
          require ADMIN.
        </p>
      </div>

      {error && (
        <div className="border border-alert/60 bg-alert/10 px-4 py-3 font-mono text-xs text-alert">
          {error}
        </div>
      )}

      {canWrite && (
        <TerminalPanel title="Upsert Entry" windowId="CFG-EDIT">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block font-mono text-[10px] uppercase tracking-[0.2em] text-dim">
                  Key
                </label>
                <input
                  value={key}
                  onChange={(e) => setKey(e.target.value)}
                  placeholder="max_fps"
                  className="w-full border border-line bg-panel-raised px-3 py-2 font-mono text-sm text-bone outline-none focus:border-amber"
                  required
                />
              </div>
              <div>
                <label className="mb-1 block font-mono text-[10px] uppercase tracking-[0.2em] text-dim">
                  Value (JSON)
                </label>
                <input
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                  placeholder="30"
                  className="w-full border border-line bg-panel-raised px-3 py-2 font-mono text-sm text-bone outline-none focus:border-amber"
                  required
                />
              </div>
            </div>
            {formError && (
              <p className="border border-alert/60 bg-alert/10 px-3 py-2 font-mono text-xs text-alert">
                {formError}
              </p>
            )}
            <Button type="submit" disabled={submitting}>
              {submitting ? "Saving..." : "Save Entry"}
            </Button>
          </form>
        </TerminalPanel>
      )}

      <TerminalPanel title="Configuration Entries" windowId="CFG-LIST">
        {loading ? (
          <p className="font-mono text-xs text-dim">Loading...</p>
        ) : entries.length === 0 ? (
          <p className="font-mono text-xs text-dim">No configuration entries yet.</p>
        ) : (
          <table className="w-full border-collapse font-mono text-xs">
            <thead>
              <tr className="border-b border-line text-left text-dim">
                <th className="pb-2 font-normal uppercase tracking-wider">Key</th>
                <th className="pb-2 font-normal uppercase tracking-wider">Value</th>
                <th className="pb-2 font-normal uppercase tracking-wider">Updated</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.key} className="border-b border-line/50 text-bone">
                  <td className="py-2 pr-4">{entry.key}</td>
                  <td className="py-2 pr-4 text-dim">{JSON.stringify(entry.value)}</td>
                  <td className="py-2 text-dim">{formatTimestamp(entry.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </TerminalPanel>
    </div>
  );
}

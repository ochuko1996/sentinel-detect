export function StatReadout({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="border border-line bg-panel/60 p-4">
      <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-dim">{label}</p>
      <p className="mt-1 font-display text-3xl font-bold text-bone">{value}</p>
      {sub && <p className="mt-1 font-mono text-[10px] text-dim">{sub}</p>}
    </div>
  );
}

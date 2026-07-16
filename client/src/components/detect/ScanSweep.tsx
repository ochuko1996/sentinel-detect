export function ScanSweep() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      <div
        className="absolute inset-x-0 h-24 animate-scan"
        style={{
          background:
            "linear-gradient(180deg, transparent, rgba(255,176,0,0.35) 45%, rgba(255,176,0,0.7) 50%, rgba(255,176,0,0.35) 55%, transparent)",
        }}
      />
      <div className="absolute inset-0 bg-amber/5" />
    </div>
  );
}

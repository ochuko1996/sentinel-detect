export function ClassificationBar() {
  return (
    <div className="relative z-50 flex h-6 items-center justify-center overflow-hidden bg-alert/90 text-void">
      <div
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{
          backgroundImage:
            "repeating-linear-gradient(-45deg, rgba(7,9,10,0.5) 0, rgba(7,9,10,0.5) 10px, transparent 10px, transparent 20px)",
        }}
      />
      <p className="relative font-display text-[11px] font-semibold uppercase tracking-[0.35em]">
        RESTRICTED ACCESS — SENTINEL DETECT SURVEILLANCE NETWORK — AUTHORIZED PERSONNEL ONLY
      </p>
    </div>
  );
}

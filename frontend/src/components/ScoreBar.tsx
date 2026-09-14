export default function ScoreBar({
  label,
  value,
  max,
  highlight
}: {
  label: string;
  value: number;
  max: number;
  highlight?: boolean;
}) {
  const pct = Math.max(4, Math.min(100, (value / max) * 100));
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <span
        style={{
          width: 90,
          fontSize: 12,
          color: "var(--text-muted)",
          flexShrink: 0
        }}
      >
        {label}
      </span>
      <div
        style={{
          flex: 1,
          height: 8,
          borderRadius: 4,
          background: "var(--surface-line)",
          overflow: "hidden"
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            borderRadius: 4,
            background: highlight ? "var(--pulse)" : "var(--text-faint)",
            transition: "width 0.4s ease"
          }}
        />
      </div>
      <span className="mono" style={{ fontSize: 12, width: 44, textAlign: "right" }}>
        {value}
      </span>
    </div>
  );
}

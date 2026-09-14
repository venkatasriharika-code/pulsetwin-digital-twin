import type { Severity } from "../api/types";

const config: Record<Severity, { label: string; color: string }> = {
  critical: { label: "Critical", color: "var(--critical)" },
  serious: { label: "Serious", color: "var(--serious)" },
  mild: { label: "Mild", color: "var(--mild)" }
};

export default function SeverityBadge({ severity }: { severity: Severity }) {
  const c = config[severity];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        fontSize: 12,
        color: c.color
      }}
    >
      <span
        style={{
          width: 7,
          height: 7,
          borderRadius: "50%",
          background: c.color,
          display: "inline-block"
        }}
      />
      {c.label}
    </span>
  );
}

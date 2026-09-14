interface Props { label: string; value: string; unit?: string; emphasis?: boolean; tone?: "default" | "critical" | "serious" | "mild"; trend?: string; }
const toneColor: Record<string, string> = { default: "var(--text)", critical: "var(--critical)", serious: "var(--serious)", mild: "var(--mild)" };
export default function KpiTile({ label, value, unit, emphasis, tone = "default", trend }: Props) {
  return <div className={`card kpi-tile ${emphasis ? "kpi-emphasis" : ""}`}><span className="kpi-label">{label}</span><span className="mono kpi-value" style={{color: emphasis ? "var(--pulse)" : toneColor[tone]}}>{value}{unit && <span className="kpi-unit">{unit}</span>}</span>{trend && <span className="kpi-trend">{trend}</span>}</div>;
}

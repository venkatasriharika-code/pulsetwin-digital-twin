import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { WardStatus } from "../api/types";
import KpiTile from "../components/KpiTile";

export default function CommandCenter() {
  const [status, setStatus] = useState<WardStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const load = () => { setLoading(true); setError(null); api.getWardStatus().then(setStatus).catch((e: ApiError) => setError(e.message)).finally(() => setLoading(false)); };
  useEffect(() => { load(); const timer = setInterval(load, 30000); return () => clearInterval(timer); }, []);
  return <div>
    <header className="page-header dashboard-header"><div><div className="eyebrow">PULSETWIN / OPERATIONS</div><h1>Command Center</h1><p>Live digital twin of the emergency department · Synthetic telemetry · <span className="live-dot">● LIVE</span></p></div><div className="header-actions"><span className="sync-label">SYNCED {status ? new Date(status.timestamp).toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"}) : "—"}</span><button className="btn-ghost" onClick={load}>↻ Refresh</button><Link className="btn-primary" to="/ask">Ask the twin →</Link></div></header>
    {loading && !status && <div className="state-loading">Reading ward telemetry…</div>}
    {error && !status && <div className="state-error">{error}<div><button className="btn-ghost" onClick={load}>Retry</button></div></div>}
    {status && <>
      <section className="kpi-grid">
        <KpiTile label="Arrivals / hour" value={String(status.arrivalsPerHour)} unit="patients" trend="+12% vs baseline" />
        <KpiTile label="Patients in system" value={String(status.patientsInSystem)} trend={`${status.queueLength} in queues`} />
        <KpiTile label="Average wait" value={String(status.avgWaitMinutes)} unit="min" emphasis trend="Target < 30 min" />
        <KpiTile label="Critical wait" value={String(status.criticalWaitMinutes)} unit="min" tone="critical" trend="Target < 15 min" />
        <KpiTile label="Throughput" value={String(status.throughputPerHour)} unit="/ hour" trend="84% of arrivals" />
        <KpiTile label="Beds available" value={String(status.bedsAvailable)} unit={`of ${status.beds}`} tone="serious" trend="72% occupied" />
      </section>
      <section className="dashboard-grid main-dashboard-grid">
        <div className="card trend-card"><div className="section-heading"><div><div className="eyebrow">DEMAND & PRESSURE</div><h2>Ward pressure over today</h2></div><span className="status-pill warning">SURGE WATCH</span></div><TrendChart points={status.trend} /><div className="legend"><span><i className="legend-line teal"/>Arrivals / hr</span><span><i className="legend-line amber"/>Avg wait</span><span><i className="legend-line red"/>Utilization</span></div></div>
        <div className="card acuity-card"><div className="eyebrow">ACUITY MIX</div><h2>Who is waiting</h2><div className="donut-wrap"><div className="donut" style={{background:`conic-gradient(var(--critical) 0 ${status.acuityMix.critical*100}%, var(--serious) ${status.acuityMix.critical*100}% ${(status.acuityMix.critical+status.acuityMix.serious)*100}%, var(--mild) ${(status.acuityMix.critical+status.acuityMix.serious)*100}% 100%)`}}><div><strong>100%</strong><small>patients</small></div></div><div className="acuity-legend"><AcuityRow label="Critical" value={status.acuityMix.critical} color="var(--critical)"/><AcuityRow label="Serious" value={status.acuityMix.serious} color="var(--serious)"/><AcuityRow label="Mild" value={status.acuityMix.mild} color="var(--mild)"/></div></div></div>
      </section>
      <section className="dashboard-grid lower-dashboard-grid"><div className="card"><div className="section-heading"><div><div className="eyebrow">CAPACITY MAP</div><h2>Resource utilization</h2></div><Link to="/ward" className="text-link">Open twin →</Link></div><div className="resource-list">{status.resources.map(r=><div className="resource-row" key={r.name}><div className="resource-name"><span className={`resource-dot ${r.status}`}/><span>{r.name}</span><span className="mono resource-count">{r.used}/{r.total}</span></div><div className="meter"><span className={r.status} style={{width:`${Math.min(100,r.utilizationPct)}%`}}/></div><span className={`mono utilization ${r.status}`}>{r.utilizationPct}%</span></div>)}</div></div><div className="card"><div className="section-heading"><div><div className="eyebrow">ACTIVE SIGNALS</div><h2>What needs attention</h2></div><span className="mono signal-count">{status.alerts.length} signals</span></div><div className="alert-list">{status.alerts.map((alert,i)=><div className="alert-item" key={alert}><span className={`alert-icon ${i===0?'red':i===1?'amber':'teal'}`}>{i===0?'!':i===1?'↑':'◷'}</span><span>{alert}</span><span className="arrow">→</span></div>)}</div><Link className="action-callout" to="/ask"><span><strong>Test a response</strong><small>Ask “what if?” and compare interventions</small></span><span>↗</span></Link></div></section>
    </>}
  </div>;
}
function AcuityRow({label,value,color}:{label:string;value:number;color:string}) { return <div className="acuity-row"><span className="acuity-label"><i style={{background:color}}/>{label}</span><strong>{Math.round(value*100)}%</strong></div>; }
function TrendChart({points}:{points:WardStatus["trend"]}) { const max=Math.max(...points.map(p=>Math.max(p.arrivals,p.waitMinutes,p.utilizationPct/3)),1); const line=(key:keyof typeof points[number], color:string, scale=1)=>points.map((p,i)=>`${(i/(points.length-1))*100},${100-(Number(p[key])*scale/max)*100}`).join(" "); return <div className="trend-chart"><svg viewBox="0 0 100 100" preserveAspectRatio="none"><path d="M 0 25 H 100 M 0 50 H 100 M 0 75 H 100" className="chart-grid"/><polyline points={line("arrivals","teal",1)} className="chart-line teal"/><polyline points={line("waitMinutes","amber",1)} className="chart-line amber"/><polyline points={line("utilizationPct","red",.33)} className="chart-line red"/></svg><div className="chart-labels">{points.map(p=><span key={p.label}>{p.label}</span>)}</div></div>; }

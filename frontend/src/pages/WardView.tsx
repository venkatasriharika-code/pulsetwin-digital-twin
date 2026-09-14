import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { api, ApiError } from "../api/client";
import type { LiveSimulationSnapshot, PipelineStage, WardTwinState } from "../api/types";
import SeverityBadge from "../components/SeverityBadge";

const STAGES: { key: PipelineStage; label: string }[] = [
  { key: "ARRIVED", label: "Arrived" },
  { key: "TRIAGE", label: "Triage" },
  { key: "WAITING_FOR_DOCTOR", label: "Waiting" },
  { key: "DOCTOR", label: "Doctor" },
  { key: "TESTING", label: "Testing" },
  { key: "TREATMENT", label: "Treatment" },
  { key: "WAITING_FOR_BED", label: "Bed queue" },
  { key: "BED", label: "Bed" },
  { key: "DISCHARGED", label: "Discharged" },
];

const FALLBACK_COUNTS: Record<string, number> = {
  ARRIVED: 4,
  TRIAGE: 6,
  WAITING_FOR_DOCTOR: 8,
  DOCTOR: 5,
  TESTING: 4,
  TREATMENT: 6,
  WAITING_FOR_BED: 3,
  BED: 24,
  DISCHARGED: 7,
};

const FALLBACK_PATIENTS = [
  { id: "PT-1042", severity: "critical", stage: "TRIAGE" as PipelineStage, waitMinutes: 8, x: 26, y: 37, room: "Triage 01", complaint: "Chest pain", vitals: "HR 112 · SpO₂ 94%", assigned: "Nurse A. Chen" },
  { id: "PT-1048", severity: "serious", stage: "DOCTOR" as PipelineStage, waitMinutes: 21, x: 43, y: 37, room: "Exam 03", complaint: "Respiratory distress", vitals: "HR 96 · SpO₂ 91%", assigned: "Dr. M. Patel" },
  { id: "PT-1053", severity: "mild", stage: "WAITING_FOR_DOCTOR" as PipelineStage, waitMinutes: 14, x: 54, y: 42, room: "Waiting zone", complaint: "Laceration", vitals: "Stable · pain 4/10", assigned: "Queue position 03" },
  { id: "PT-1060", severity: "serious", stage: "TREATMENT" as PipelineStage, waitMinutes: 32, x: 67, y: 39, room: "Treatment 02", complaint: "Fracture follow-up", vitals: "BP 128/76 · Stable", assigned: "Nurse R. Cole" },
  { id: "PT-1064", severity: "mild", stage: "BED" as PipelineStage, waitMinutes: 6, x: 74, y: 63, room: "Ward bed W-07", complaint: "Observation", vitals: "HR 78 · SpO₂ 98%", assigned: "Ward team B" },
  { id: "PT-1067", severity: "serious", stage: "BED" as PipelineStage, waitMinutes: 12, x: 87, y: 74, room: "Ward bed W-12", complaint: "Post-operative care", vitals: "BP 118/70 · Stable", assigned: "Ward team A" },
];

const BED_NODES = [
  { id: "W-01", label: "Bed 01", x: 73, y: 57, occupied: true, patient: "PT-1064", acuity: "mild" },
  { id: "W-02", label: "Bed 02", x: 83, y: 57, occupied: false, patient: "—", acuity: "available" },
  { id: "W-03", label: "Bed 03", x: 73, y: 68, occupied: true, patient: "PT-1067", acuity: "serious" },
  { id: "W-04", label: "Bed 04", x: 83, y: 68, occupied: true, patient: "PT-1070", acuity: "serious" },
  { id: "W-05", label: "Bed 05", x: 73, y: 79, occupied: true, patient: "PT-1073", acuity: "mild" },
  { id: "W-06", label: "Bed 06", x: 83, y: 79, occupied: false, patient: "—", acuity: "available" },
];

type SelectedEntity =
  | { kind: "patient"; id: string; title: string; subtitle: string; details: Array<[string, string]>; x: number; y: number; severity: string }
  | { kind: "bed"; id: string; title: string; subtitle: string; details: Array<[string, string]>; x: number; y: number; severity: string }
  | null;

export default function WardView({
  selection,
}: {
  selection: { scenarioId: string; candidateId: string } | null;
}) {
  const [state, setState] = useState<WardTwinState | null>(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState<string | null>(null);
  const [selectedEntity, setSelectedEntity] = useState<SelectedEntity>(null);
  const [liveSnapshot, setLiveSnapshot] = useState<LiveSimulationSnapshot | null>(null);
  const [liveStatus, setLiveStatus] = useState<"offline" | "connecting" | "running" | "stopped">("offline");
  const [socket, setSocket] = useState<WebSocket | null>(null);

  const load = () => {
    if (!selection) {
      setStatus("preview");
      return;
    }
    setStatus("loading");
    api
      .getWardTwinState(selection.scenarioId, selection.candidateId)
      .then((nextState) => {
        setState(nextState);
        setStatus("ready");
      })
      .catch((e: ApiError) => {
        setError(e.message);
        setStatus("error");
      });
  };

  useEffect(load, [selection]);
  useEffect(() => setSelectedEntity(null), [selection]);
  useEffect(() => () => socket?.close(), [socket]);

  const startLiveSimulation = () => {
    socket?.close();
    const base = import.meta.env.VITE_API_BASE_URL || window.location.origin;
    const wsUrl = base.replace(/^http/, "ws") + "/ws/simulation";
    const ws = new WebSocket(wsUrl);
    setSocket(ws); setLiveStatus("connecting");
    ws.onopen = () => { setLiveStatus("running"); ws.send(JSON.stringify({ action: "tick", demandMultiplier: 1, tickMinutes: 5, tickSeconds: 1 })); };
    ws.onmessage = (event) => { const message = JSON.parse(event.data); if (message.snapshot) setLiveSnapshot(message.snapshot); };
    ws.onclose = () => setLiveStatus("stopped"); ws.onerror = () => setLiveStatus("offline");
  };
  const sendLiveAction = (action: string) => { if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ action })); };

  const counts = liveSnapshot?.stageCounts ?? state?.stageCounts ?? FALLBACK_COUNTS;
  const visiblePatients = liveSnapshot?.patients ?? state?.patients ?? [];
  const mapPatients = useMemo(() => {
    if (!visiblePatients.length) return FALLBACK_PATIENTS;
    return visiblePatients.slice(0, 8).map((patient, index) => ({
      ...patient,
      x: [26, 43, 54, 67, 74, 87, 58, 35][index] ?? 50,
      y: [37, 37, 42, 39, 63, 74, 57, 64][index] ?? 45,
      room: STAGES.find((stage) => stage.key === patient.stage)?.label ?? "Clinical core",
      complaint: "Active care pathway",
      vitals: patient.severity === "critical" ? "Immediate review" : "Telemetry stable",
      assigned: "Care team on duty",
    }));
  }, [visiblePatients]);

  const openPatient = (patient: (typeof FALLBACK_PATIENTS)[number]) => {
    setSelectedEntity({
      kind: "patient",
      id: patient.id,
      title: patient.id,
      subtitle: `${patient.room} · ${capitalize(patient.severity)} acuity`,
      details: [
        ["Current stage", STAGES.find((stage) => stage.key === patient.stage)?.label ?? patient.stage],
        ["Primary concern", patient.complaint],
        ["Vitals", patient.vitals],
        ["Wait time", `${patient.waitMinutes} minutes`],
        ["Assigned", patient.assigned],
      ],
      x: patient.x,
      y: patient.y,
      severity: patient.severity,
    });
  };

  const openBed = (bed: (typeof BED_NODES)[number]) => {
    const linkedPatient = mapPatients.find((patient) => patient.id === bed.patient);
    setSelectedEntity({
      kind: "bed",
      id: bed.id,
      title: bed.label,
      subtitle: bed.occupied ? `Occupied · ${bed.patient}` : "Available for assignment",
      details: [
        ["Ward zone", "North inpatient pod"],
        ["Status", bed.occupied ? "Occupied" : "Available"],
        ["Patient", bed.occupied ? bed.patient : "No patient assigned"],
        ["Acuity", bed.occupied ? capitalize(bed.acuity) : "—"],
        ["Telemetry", linkedPatient ? linkedPatient.vitals : "Ready · monitor online"],
      ],
      x: bed.x,
      y: bed.y,
      severity: bed.occupied ? bed.acuity : "available",
    });
  };

  return (
    <div>
      <PageHeader label={state?.appliedLabel} preview={!selection} />
      {selection && status === "loading" && !state && (
        <div className="state-loading">Rendering virtual patients from simulation state…</div>
      )}
      {selection && status === "error" && !state && (
        <div className="state-error">
          {error}
          <button className="btn-ghost" onClick={load}>Retry</button>
        </div>
      )}
      <div className="twin-toolbar">
        <span className={`status-pill ${liveStatus === "running" ? "healthy" : "warning"}`}>● {liveStatus === "running" ? "LIVE STREAM" : "STATIC SNAPSHOT"}</span>
        <span>Horizon: <strong>{liveSnapshot?.simulatedMinutes ?? state?.simulatedMinutes ?? 30} min</strong></span>
        <span>Queue: <strong>{liveSnapshot?.queueMetrics.queueLength ?? counts.WAITING_FOR_DOCTOR + counts.WAITING_FOR_BED}</strong></span>
        {liveSnapshot && <span>Avg wait: <strong>{liveSnapshot.queueMetrics.avgWaitMinutes} min</strong></span>}
        <span className="twin-toolbar-spacer" />
        {liveStatus !== "running" && <button className="btn-primary" onClick={startLiveSimulation}>▶ Start live simulation</button>}
        {liveStatus === "running" && <><button className="btn-ghost" onClick={() => sendLiveAction("tick")}>＋ Advance 5 min</button><button className="btn-ghost" onClick={() => sendLiveAction("reset")}>↻ Reset</button><button className="btn-ghost" onClick={() => sendLiveAction("stop")}>■ Stop</button></>}
        {selection && <button className="btn-ghost" onClick={load}>↻ Re-run snapshot</button>}
      </div>
      <HospitalFloorPlan counts={counts} patients={mapPatients} selectedEntity={selectedEntity} onPatientClick={openPatient} onBedClick={openBed} onClose={() => setSelectedEntity(null)} />
      {state && <SimulationDetails state={state} visiblePatients={visiblePatients} />}
      {liveSnapshot && <div className="card live-metrics"><div className="section-heading"><div><div className="eyebrow">REAL-TIME QUEUEING ENGINE</div><h2>Dynamic operating metrics</h2></div><span className="mono">{liveSnapshot.queueMetrics.arrivals} arrivals · {liveSnapshot.queueMetrics.discharged} discharged</span></div><div className="live-metric-grid"><div><span>Doctor queue</span><strong>{liveSnapshot.queueMetrics.doctorQueue}</strong></div><div><span>Bed queue</span><strong>{liveSnapshot.queueMetrics.bedQueue}</strong></div><div><span>Throughput</span><strong>{liveSnapshot.queueMetrics.throughputPerHour}<em>/hr</em></strong></div><div><span>Doctor utilization</span><strong>{liveSnapshot.resourceUtilization.doctors}%</strong></div><div><span>Bed utilization</span><strong>{liveSnapshot.resourceUtilization.beds}%</strong></div></div>{liveSnapshot.anomaly && <div className="surge-strip"><span>Predictive surge risk</span><strong>{Math.round(liveSnapshot.anomaly.surgeProbability*100)}%</strong><small>{liveSnapshot.anomaly.isAnomalous ? "Operational anomaly detected" : "Within recent operating range"}</small></div>}{liveSnapshot.anomaly?.alerts.map((alert) => <div className={`live-alert ${alert.level}`} key={alert.id}><b>{alert.title}</b><span>{alert.message}</span><small>{alert.recommendedAction}</small></div>)}</div>}
    </div>
  );
}

function PageHeader({ label, preview }: { label?: string; preview: boolean }) {
  return (
    <header className="page-header">
      <div className="eyebrow">DIGITAL TWIN / LIVE PATIENT FLOW</div>
      <h1>Ward View</h1>
      <p>{label ? <>Showing <span className="quoted">{label}</span> · click a patient or bed to inspect its live details.</> : preview ? "Top-down ground-floor map of the hospital operations twin. Click a patient or bed to inspect its live details." : "Select a recommendation to inspect the virtual ward."}</p>
    </header>
  );
}

function HospitalFloorPlan({
  counts,
  patients,
  selectedEntity,
  onPatientClick,
  onBedClick,
  onClose,
}: {
  counts: Record<string, number>;
  patients: Array<(typeof FALLBACK_PATIENTS)[number]>;
  selectedEntity: SelectedEntity;
  onPatientClick: (patient: (typeof FALLBACK_PATIENTS)[number]) => void;
  onBedClick: (bed: (typeof BED_NODES)[number]) => void;
  onClose: () => void;
}) {
  const bedCount = Math.max(18, Math.min(32, counts.BED ?? 24));
  return (
    <section className="hospital-floorplan" aria-label="Top-down Minecraft-style hospital ground floor">
      <div className="floorplan-toolbar">
        <div><span className="floorplan-kicker">GROUND FLOOR / TOP-DOWN TWIN</span><h2>Emergency Department · Block map</h2></div>
        <div className="floorplan-hints"><span><b>Click</b> patients / beds</span><span><i className="map-live-dot" /> live simulation</span><span>{bedCount} beds tracked</span></div>
      </div>
      <div className="floorplan-viewport">
        <div className="floorplan-site">
          <div className="site-label main-label">PULSETWIN GENERAL HOSPITAL</div>
          <div className="site-label north-label">NORTH</div>
          <div className="north-arrow">↑</div>
          <div className="outside-zone outside-north" /><div className="outside-zone outside-west" /><div className="outside-zone outside-south" />
          <div className="driveway driveway-west" /><div className="driveway driveway-south" />
          <div className="room room-reception"><RoomLabel code="A01" title="Reception" meta="Check-in" /><div className="counter-block" /><div className="counter-block" /><div className="queue-block"><i /><i /><i /><i /></div><StaffMarker type="reception" /></div>
          <div className="room room-emergency"><RoomLabel code="A02" title="Emergency entry" meta={`${counts.ARRIVED ?? 4} arrivals`} /><div className="entry-mat" /><div className="double-door" /><span className="door-label">AMBULANCE BAY</span><AmbulanceMarker /></div>
          <div className="room room-triage"><RoomLabel code="B01" title="Triage" meta={`${counts.TRIAGE ?? 6} in flow`} /><div className="triage-desk" /><div className="exam-table table-one" /><div className="exam-table table-two" /><StaffMarker type="nurse" /></div>
          <div className="room room-waiting"><RoomLabel code="B02" title="Waiting hall" meta={`${counts.WAITING_FOR_DOCTOR ?? 8} waiting`} /><div className="waiting-seat seat-one" /><div className="waiting-seat seat-two" /><div className="waiting-seat seat-three" /><div className="waiting-seat seat-four" /><div className="water-block" /></div>
          <div className="room room-exam"><RoomLabel code="B03" title="Exam rooms" meta="04 rooms" /><div className="exam-room-grid"><i /><i /><i /><i /></div><StaffMarker type="doctor" /></div>
          <div className="room room-treatment"><RoomLabel code="B04" title="Treatment" meta={`${counts.TREATMENT ?? 6} active`} /><div className="treatment-pod pod-one" /><div className="treatment-pod pod-two" /><div className="monitor-wall" /><StaffMarker type="nurse" /></div>
          <div className="room room-pharmacy"><RoomLabel code="C01" title="Pharmacy" meta="18 orders" /><div className="shelf-block shelf-one" /><div className="shelf-block shelf-two" /><div className="pharmacy-counter" /><StaffMarker type="pharmacist" /></div>
          <div className="room room-resources"><RoomLabel code="C02" title="Resources + lab" meta="72% stocked" /><div className="resource-crates"><i /><i /><i /><i /><i /><i /></div><div className="lab-panel"><b>LAB</b><span>READY</span></div></div>
          <div className="room room-wards"><RoomLabel code="D01" title="Inpatient wards" meta={`${bedCount} beds`} /><div className="ward-corridor" /><div className="ward-nurse-station" /><div className="ward-bed-grid">{BED_NODES.map((bed) => <BedMarker key={bed.id} bed={bed} onClick={() => onBedClick(bed)} />)}</div><div className="ward-room-label">NORTH POD · CLICK A BED</div></div>
          <div className="floor-corridor corridor-main" /><div className="floor-corridor corridor-cross" /><div className="floor-arrow arrow-one">→</div><div className="floor-arrow arrow-two">→</div><div className="floor-arrow arrow-three">↓</div>
          <div className="patient-layer">{patients.map((patient) => <PatientMarker key={patient.id} patient={patient} onClick={() => onPatientClick(patient)} />)}</div>
          <div className="staff-layer"><StaffMarker type="doctor" className="staff-1" /><StaffMarker type="nurse" className="staff-2" /><StaffMarker type="nurse" className="staff-3" /></div>
          <div className="exit-marker">EXIT <b>→</b></div><div className="ambulance-route"><span /><span /><span /></div>
          {selectedEntity && <EntityPopover entity={selectedEntity} onClose={onClose} />}
        </div>
      </div>
      <div className="floorplan-legend"><span><i className="legend-square patient-square" />Patient — click for detail</span><span><i className="legend-square bed-square" />Bed — click for occupancy</span><span><i className="legend-square staff-square" />Staff on floor</span><span><i className="legend-square route-square" />Movement route</span></div>
    </section>
  );
}

function RoomLabel({ code, title, meta }: { code: string; title: string; meta: string }) {
  return <div className="room-label"><span className="room-code">{code}</span><div><strong>{title}</strong><small>{meta}</small></div></div>;
}

function PatientMarker({ patient, onClick }: { patient: (typeof FALLBACK_PATIENTS)[number]; onClick: () => void }) {
  return <button type="button" className={`map-patient ${patient.severity}`} style={{ left: `${patient.x}%`, top: `${patient.y}%` }} onClick={onClick} title={`Open ${patient.id} details`}><span className="voxel-person"><i className="voxel-head" /><i className="voxel-torso" /><i className="voxel-leg leg-a" /><i className="voxel-leg leg-b" /></span><span className="map-patient-tag">{patient.id}</span></button>;
}

function BedMarker({ bed, onClick }: { bed: (typeof BED_NODES)[number]; onClick: () => void }) {
  return <button type="button" className={`map-bed ${bed.occupied ? bed.acuity : "available"}`} style={{ left: `${bed.x}%`, top: `${bed.y}%` }} onClick={onClick} title={`Open ${bed.label} details`}><span className="voxel-bed"><i className="bed-sheet" /><i className="bed-pillow" /><i className="bed-rail" /></span><span className="map-bed-tag">{bed.id}</span></button>;
}

function StaffMarker({ type, className = "" }: { type: string; className?: string }) {
  return <span className={`map-staff ${type} ${className}`} title={`${type} on floor`}><i className="voxel-head" /><i className="voxel-torso" /><i className="voxel-leg leg-a" /><i className="voxel-leg leg-b" /></span>;
}

function AmbulanceMarker() {
  return <span className="map-ambulance"><i className="ambulance-red-cross">+</i><i className="ambulance-wheel wheel-a" /><i className="ambulance-wheel wheel-b" /></span>;
}

function EntityPopover({ entity, onClose }: { entity: Exclude<SelectedEntity, null>; onClose: () => void }) {
  const left = Math.min(entity.x + 2, 72);
  const top = entity.y > 62 ? entity.y - 24 : entity.y + 5;
  return <div className={`entity-popover ${entity.kind}-popover`} style={{ left: `${left}%`, top: `${top}%` }} role="dialog" aria-label={`${entity.title} details`}><div className="popover-notch" /><div className="popover-head"><div><span className="popover-kind">{entity.kind === "patient" ? "PATIENT DETAIL" : "BED DETAIL"}</span><h3>{entity.title}</h3><p>{entity.subtitle}</p></div><button type="button" className="popover-close" onClick={onClose} aria-label="Close details">×</button></div><div className="popover-details">{entity.details.map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>{entity.kind === "patient" && <div className={`popover-status ${entity.severity}`}><i /> live care pathway · {capitalize(entity.severity)} priority</div>}{entity.kind === "bed" && <div className={`popover-status ${entity.severity}`}><i /> {entity.severity === "available" ? "ready for assignment" : "telemetry online"}</div>}</div>;
}

function SimulationDetails({ state, visiblePatients }: { state: WardTwinState; visiblePatients: WardTwinState["patients"] }) {
  return <><div className="dashboard-grid ward-lower"><div className="card"><div className="eyebrow">EVENT STREAM</div><h2>Patient flow trace</h2><div className="event-stream">{state.eventLog.map((event) => <div key={event}><span className="event-dot" />{event}</div>)}</div></div><div className="card"><div className="eyebrow">SIMULATION RESOURCES</div><h2>Applied configuration</h2>{Object.entries(state.resourceUtilization).map(([name, value]) => <div className="resource-row" key={name}><div className="resource-name"><span>{name}</span><strong className="mono">{value}%</strong></div><div className="meter"><span className={value >= 90 ? "strained" : value >= 78 ? "watch" : "healthy"} style={{ width: `${value}%` }} /></div></div>)}<div className="twin-note">Click targets in the floor plan are reading the same simulated patient state used to score the recommendation.</div></div></div><div className="card patient-table"><div className="section-heading"><div><div className="eyebrow">PATIENT MANIFEST</div><h2>Virtual patients</h2></div><span className="mono">{visiblePatients.length} shown</span></div><div className="manifest-grid">{visiblePatients.slice(0, 18).map((patient) => <div key={patient.id}><span className="mono">{patient.id}</span><SeverityBadge severity={patient.severity} /><span>{STAGES.find((stage) => stage.key === patient.stage)?.label}</span><small>{patient.waitMinutes}m wait</small></div>)}</div></div></>;
}

function capitalize(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

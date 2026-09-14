import { useState } from "react";
import type { CSSProperties } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { ParsedScenario } from "../api/types";

const examples = [
  "What if patient arrivals increase by 30% tomorrow night?",
  "I have two extra doctors. Where should I put them?",
  "Should I add beds or doctors for the weekend surge?"
];

type ControlKey = "arrivalsPerHour" | "doctors" | "nurses" | "beds" | "triageNurses" | "ctCapacity" | "labCapacity";
type Controls = Record<ControlKey, number>;

const initialControls: Controls = { arrivalsPerHour: 25, doctors: 5, nurses: 8, beds: 20, triageNurses: 2, ctCapacity: 1, labCapacity: 2 };
const controlDefinitions: { key: ControlKey; label: string; hint: string; min: number; max: number; unit: string; tone?: string }[] = [
  { key: "arrivalsPerHour", label: "Patient demand", hint: "Expected arrivals", min: 0, max: 80, unit: "patients / hr", tone: "teal" },
  { key: "doctors", label: "Doctors", hint: "Available on shift", min: 0, max: 20, unit: "clinicians" },
  { key: "nurses", label: "Nurses", hint: "Available on shift", min: 0, max: 30, unit: "clinicians" },
  { key: "beds", label: "Treatment beds", hint: "Open capacity", min: 0, max: 60, unit: "beds", tone: "amber" },
  { key: "triageNurses", label: "Triage stations", hint: "Front-door capacity", min: 0, max: 10, unit: "stations" },
  { key: "ctCapacity", label: "CT scanners", hint: "Available machines", min: 0, max: 4, unit: "machines", tone: "red" },
  { key: "labCapacity", label: "Lab benches", hint: "Diagnostics capacity", min: 0, max: 8, unit: "benches" }
];

export default function AskScenario({ onEvaluated }: { onEvaluated: (scenario: ParsedScenario) => void }) {
  const [question, setQuestion] = useState("");
  const [parsed, setParsed] = useState<ParsedScenario | null>(null);
  const [controls, setControls] = useState<Controls>(initialControls);
  const [status, setStatus] = useState<"idle" | "parsing" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  async function handleAsk(value: string) {
    const text = value.trim();
    if (!text) return;
    setStatus("parsing"); setError(null);
    try { const result = await api.parseScenario(text); setParsed(result); setStatus("idle"); }
    catch (requestError) { setError((requestError as ApiError).message); setStatus("error"); }
  }

  function updateControl(key: ControlKey, value: number) { setControls((current) => ({ ...current, [key]: value })); }

  function runScenario() {
    if (!parsed) return;
    const configured: ParsedScenario = { ...parsed, ...controls };
    onEvaluated(configured);
    navigate("/recommendation");
  }

  return <div>
    <header className="page-header ask-header"><div><div className="eyebrow">SCENARIO BUILDER / MANUAL + CONVERSATIONAL</div><h1>Ask the Twin</h1><p>Describe a situation, then tune the virtual ward before running the simulation.</p></div><div className="data-mode-badge"><span className="live-dot">●</span><span>DATA MODE</span><strong>SYNTHETIC OPERATIONAL TWIN</strong></div></header>
    <section className="ask-layout">
      <div className="ask-main">
        <form className="question-card card" onSubmit={(event)=>{event.preventDefault();handleAsk(question);}}><div className="eyebrow">01 / ASK A WHAT-IF QUESTION</div><h2>What do you want to test?</h2><div className="question-row"><input value={question} onChange={(event)=>setQuestion(event.target.value)} placeholder="e.g. What if tomorrow night has 30% more patients?"/><button className="btn-primary" type="submit" disabled={status === "parsing" || !question.trim()}>{status === "parsing" ? "Parsing…" : "Interpret question"}</button></div><div className="example-list">{examples.map((example)=><button type="button" className="example-chip" key={example} onClick={()=>{setQuestion(example);handleAsk(example);}}>{example}</button>)}</div></form>
        <section className="card controls-card"><div className="section-heading"><div><div className="eyebrow">02 / SET VIRTUAL WARD CONDITIONS</div><h2>Manual scenario controls</h2><p className="section-subtitle">Move the meters to test a different operating picture.</p></div><button className="btn-ghost reset-controls" type="button" onClick={()=>setControls(initialControls)}>Reset defaults</button></div><div className="control-grid">{controlDefinitions.map((definition)=><ControlMeter key={definition.key} definition={definition} value={controls[definition.key]} onChange={(value)=>updateControl(definition.key,value)}/>)}</div></section>
      </div>
      <aside className="scenario-summary card"><div className="eyebrow">SCENARIO PREVIEW</div><div className="summary-status"><span className={parsed?"status-pill healthy":"status-pill warning"}>{parsed?"READY TO RUN":"WAITING FOR QUESTION"}</span></div><h2>{parsed ? parsed.timePeriod : "No scenario interpreted"}</h2><p>{parsed ? parsed.rawQuestion : "Ask a question to create the operational scenario, or adjust the virtual ward controls below."}</p><div className="summary-divider"/><div className="summary-fields"><SummaryField label="Projected arrivals" value={`${(controls.arrivalsPerHour * (1 + (parsed?.arrivalSurgePct ?? 0) / 100)).toFixed(1)} / hr`}/><SummaryField label="Arrival surge" value={`+${parsed?.arrivalSurgePct ?? 0}%`}/><SummaryField label="Objective" value={parsed?.objective === "protect_critical_wait" ? "Protect critical wait" : "Minimize waiting"}/></div><div className="summary-quick"><span>Configured resources</span><strong>{controls.doctors} doctors · {controls.nurses} nurses · {controls.beds} beds</strong></div><button className="btn-primary run-button" disabled={!parsed} onClick={runScenario}>{parsed ? "Run detailed simulation →" : "Interpret a question first"}</button><small className="honesty-note">The engine will screen candidates and validate the strongest options with reproducible simulation.</small></aside>
    </section>
    {status === "error" && <div className="state-error">{error}<button className="btn-ghost" onClick={()=>handleAsk(question)}>Retry</button></div>}
  </div>;
}

function ControlMeter({ definition, value, onChange }: { definition: typeof controlDefinitions[number]; value: number; onChange: (value: number) => void }) { const percent=((value-definition.min)/(definition.max-definition.min))*100; return <div className="control-meter"><div className="control-top"><div><strong>{definition.label}</strong><small>{definition.hint}</small></div><div className="control-number"><input type="number" min={definition.min} max={definition.max} value={value} onChange={(event)=>onChange(Math.min(definition.max,Math.max(definition.min,Number(event.target.value))))}/><span>{definition.unit}</span></div></div><input className={`range-input ${definition.tone ?? ""}`} type="range" min={definition.min} max={definition.max} value={value} style={{"--range-progress": `${percent}%`} as CSSProperties} onChange={(event)=>onChange(Number(event.target.value))}/><div className="range-labels"><span>{definition.min}</span><span>{definition.max}</span></div></div>; }
function SummaryField({label,value}:{label:string;value:string}){return <div><small>{label}</small><strong>{value}</strong></div>;}

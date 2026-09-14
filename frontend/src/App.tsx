import { useState } from "react";
import { Routes, Route } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import CommandCenter from "./pages/CommandCenter";
import AskScenario from "./pages/AskScenario";
import Recommendation from "./pages/Recommendation";
import WardView from "./pages/WardView";
import History from "./pages/History";
import Config from "./pages/Config";
import ModelLab from "./pages/ModelLab";
import Alerts from "./pages/Alerts";
import Staffing from "./pages/Staffing";
import type { ParsedScenario } from "./api/types";
export default function App() { const [scenario,setScenario]=useState<ParsedScenario|null>(null); const [selection,setSelection]=useState<{scenarioId:string;candidateId:string}|null>(null); return <div className="app-shell"><Sidebar/><main className="main-canvas"><Routes><Route path="/" element={<CommandCenter/>}/><Route path="/ask" element={<AskScenario onEvaluated={setScenario}/>}/><Route path="/recommendation" element={<Recommendation scenario={scenario} onSelectCandidate={(scenarioId,candidateId)=>setSelection({scenarioId,candidateId})}/>}/><Route path="/ward" element={<WardView selection={selection}/>}/><Route path="/config" element={<Config/>}/><Route path="/models" element={<ModelLab/>}/><Route path="/alerts" element={<Alerts/>}/><Route path="/staffing" element={<Staffing/>}/><Route path="/history" element={<History/>}/></Routes></main></div>; }

from datetime import datetime, timezone
import asyncio
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.data import BASE_CONFIG
from app.db import init_db, list_alerts, list_decisions, list_recommendations, load_config, save_alert, save_config, save_decision, save_recommendation, save_scenario
from app.models import *
from app.optimizer import evaluate
from app.queueing import screen_configuration
from app.scenario_parser import parse_question
from app.live_simulation import LiveEmergencySimulation
from app import ml
from app.reallocation import generate_recommendation

app = FastAPI(title="PulseTwin API", version="0.3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
_scenario_store: dict[str, dict] = {}

def _default_config() -> dict:
    return {"arrivalsPerHour": BASE_CONFIG.arrivals_per_hour, "doctors": BASE_CONFIG.doctors, "nurses": BASE_CONFIG.nurses, "beds": BASE_CONFIG.beds, "triageNurses": BASE_CONFIG.triage_nurses, "ctCapacity": BASE_CONFIG.ct_capacity, "labCapacity": BASE_CONFIG.lab_capacity, "minutesPerPatientDoctor": BASE_CONFIG.minutes_per_patient_doctor, "severityMix": BASE_CONFIG.severity_mix}

def _config():
    payload = load_config(_default_config())
    return BASE_CONFIG.__class__(arrivals_per_hour=payload["arrivalsPerHour"], doctors=payload["doctors"], nurses=payload["nurses"], beds=payload["beds"], triage_nurses=payload["triageNurses"], ct_capacity=payload["ctCapacity"], lab_capacity=payload["labCapacity"], minutes_per_patient_doctor=payload["minutesPerPatientDoctor"], severity_mix=payload["severityMix"])

def _status(value: float) -> str:
    return "strained" if value >= 90 else "watch" if value >= 78 else "healthy"


@app.get("/api/alerts")
def get_alerts(limit: int = Query(100, ge=1, le=500)):
    return list_alerts(limit)


@app.get("/api/recommendations")
def get_recommendations(limit: int = Query(50, ge=1, le=200)):
    return list_recommendations(limit)


@app.post("/api/recommendations/generate")
def create_recommendation(body: RecommendationGenerateRequest):
    recommendation = generate_recommendation(_config(), body.snapshot, body.surge_probability)
    save_recommendation(recommendation)
    return recommendation


@app.post("/api/recommendations/{recommendation_id}/apply")
def apply_recommendation(recommendation_id: str):
    recommendation = next((item for item in list_recommendations(200) if item["id"] == recommendation_id), None)
    if not recommendation: raise HTTPException(status_code=404, detail="Recommendation not found")
    current = load_config(_default_config()); first = recommendation["shiftRecommendations"][0]
    current["doctors"] += first["additionalDoctors"]; current["nurses"] += first["additionalNurses"]; current["beds"] += first["additionalBeds"]; updated = save_config(current)
    recommendation["status"] = "applied"; recommendation["appliedAt"] = datetime.now(timezone.utc).isoformat(); save_recommendation(recommendation)
    return {"recommendation": recommendation, "config": updated}


@app.post("/api/ml/train")
def train_ml(body: ModelTrainRequest):
    try:
        return ml.train_models(body.seed)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/ml/status")
def ml_status():
    return ml.latest() or {"status": "not-trained", "message": "Train the ED models after providing the CMS or approved hospital dataset."}


@app.post("/api/ml/predict")
def ml_predict(body: ModelPredictRequest):
    try:
        return ml.predict(body.model_dump())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.websocket("/ws/simulation")
async def simulation_socket(websocket: WebSocket):
    await websocket.accept()
    try:
        raw = await websocket.receive_json()
        config = _config()
        engine = LiveEmergencySimulation(config, seed=int(raw.get("seed", 42)), demand_multiplier=float(raw.get("demandMultiplier", 1.0)))
        tick_seconds = max(0.1, min(float(raw.get("tickSeconds", 1.0)), 5.0))
        tick_minutes = max(1.0, min(float(raw.get("tickMinutes", 5.0)), 30.0))
        await websocket.send_json({"type": "connected", "config": _default_config(), "snapshot": engine.snapshot()})
        if raw.get("action", "tick") != "stop":
            snapshot = engine.tick(tick_minutes)
            for alert in snapshot.get("anomaly", {}).get("alerts", []): save_alert(alert)
            if snapshot.get("anomaly", {}).get("surgeProbability", 0) >= .45:
                recommendation = generate_recommendation(config, snapshot); save_recommendation(recommendation); snapshot["recommendation"] = recommendation
            await websocket.send_json({"type": "tick", "snapshot": snapshot})
            await asyncio.sleep(tick_seconds)
        while True:
            message = await websocket.receive_json()
            action = message.get("action", "tick")
            if action == "stop":
                await websocket.send_json({"type": "stopped", "snapshot": engine.snapshot()}); break
            if action == "reset":
                engine = LiveEmergencySimulation(config, seed=int(message.get("seed", 42)), demand_multiplier=float(message.get("demandMultiplier", 1.0)))
            snapshot = engine.tick(tick_minutes)
            for alert in snapshot.get("anomaly", {}).get("alerts", []): save_alert(alert)
            if snapshot.get("anomaly", {}).get("surgeProbability", 0) >= .45:
                recommendation = generate_recommendation(config, snapshot); save_recommendation(recommendation); snapshot["recommendation"] = recommendation
            await websocket.send_json({"type": "tick", "snapshot": snapshot})
            await asyncio.sleep(tick_seconds)
    except WebSocketDisconnect:
        return

@app.on_event("startup")
def startup():
    init_db(); load_config(_default_config())

@app.get("/api/config", response_model=HospitalConfig)
def get_config():
    return HospitalConfig.model_validate(load_config(_default_config()))

@app.put("/api/config", response_model=HospitalConfig)
def put_config(body: HospitalConfigUpdate):
    if abs(sum(body.severity_mix.values()) - 1) > 0.01:
        raise HTTPException(status_code=400, detail="severityMix must sum to 1.0")
    if set(body.severity_mix) != {"critical", "serious", "mild"}:
        raise HTTPException(status_code=400, detail="severityMix must contain critical, serious, and mild")
    return HospitalConfig.model_validate(save_config(body.model_dump(by_alias=True)))

@app.get("/api/status", response_model=WardStatus)
def get_status():
    config = _config(); fast = screen_configuration(config.arrivals_per_hour, config.doctors, config.minutes_per_patient_doctor, config.severity_mix["critical"]); utilization = fast["doctor_utilization_pct"]; beds_available = max(0, config.beds - round(config.beds * 0.72))
    return WardStatus(timestamp=datetime.now(timezone.utc).isoformat(), arrivals_per_hour=config.arrivals_per_hour, patients_in_system=round(config.arrivals_per_hour * 1.7), doctors=config.doctors, nurses=config.nurses, beds=config.beds, beds_available=beds_available, avg_wait_minutes=fast["avg_wait_minutes"], critical_wait_minutes=fast["critical_wait_minutes"], serious_wait_minutes=round(fast["avg_wait_minutes"] * .92, 1), staff_utilization_pct=utilization, throughput_per_hour=round(config.arrivals_per_hour * .84, 1), queue_length=round(config.arrivals_per_hour * .38), acuity_mix=config.severity_mix, resources=[ResourceStatus(name="Doctors", used=round(config.doctors * utilization / 100), total=config.doctors, utilization_pct=utilization, status=_status(utilization)), ResourceStatus(name="Nurses", used=round(config.nurses * min(100, utilization * .88) / 100), total=config.nurses, utilization_pct=round(utilization * .88, 1), status=_status(utilization * .88)), ResourceStatus(name="Beds", used=config.beds - beds_available, total=config.beds, utilization_pct=72, status="watch"), ResourceStatus(name="CT", used=min(config.ct_capacity, 1), total=config.ct_capacity, utilization_pct=91 if config.ct_capacity else 0, status="strained" if config.ct_capacity else "healthy"), ResourceStatus(name="Lab", used=min(config.lab_capacity, 1), total=config.lab_capacity, utilization_pct=64 if config.lab_capacity else 0, status="healthy")], trend=[TrendPoint(label=label, arrivals=arrivals, wait_minutes=wait, utilization_pct=util) for label, arrivals, wait, util in [("06:00", 18, 21, 66), ("09:00", 24, 28, 78), ("12:00", 27, 34, 86), ("15:00", 25, 31, 82), ("18:00", 29, 39, 93), ("Now", config.arrivals_per_hour, fast["avg_wait_minutes"], utilization)]], alerts=["CT capacity is the current bottleneck", "Critical-patient wait is above the 15 min target", "Night shift demand forecast is +30%"])

@app.post("/api/scenario/parse", response_model=ParsedScenario)
def post_parse(body: ScenarioParseRequest):
    if not body.question.strip(): raise HTTPException(status_code=400, detail="question must not be empty")
    return parse_question(body.question)

@app.post("/api/scenario/evaluate", response_model=EvaluationResult)
def post_evaluate(body: ScenarioEvaluateRequest):
    scenario = body.scenario; config = _config(); baseline, candidates, recommendation, sim_cache = evaluate(scenario, config); _scenario_store[scenario.id] = {"scenario": scenario, "sims": sim_cache, "recommendation": recommendation}; save_scenario(scenario.model_dump(by_alias=True))
    return EvaluationResult(scenario=scenario, baseline=baseline, candidates=candidates, recommendation=recommendation, pipeline=["Question parsed", "12 configurations screened", "4 candidates simulated", "Severity-aware score calculated", "Recommendation generated"], computed_at=datetime.now(timezone.utc).isoformat())

@app.get("/api/ward/state", response_model=WardTwinState)
def get_ward_state(scenario_id: str = Query(..., alias="scenarioId"), candidate_id: str = Query(..., alias="candidateId")):
    entry = _scenario_store.get(scenario_id)
    if not entry or candidate_id not in entry["sims"]: raise HTTPException(status_code=404, detail="Unknown scenario or candidate. Evaluate a scenario first.")
    sim = entry["sims"][candidate_id]; event_log = ["10:01 · Patient P101 arrived", "10:04 · P101 entered triage", "10:11 · P101 assigned to doctor", "10:23 · P101 moved to testing", "10:47 · P101 entered treatment", "11:18 · P101 discharged"]
    return WardTwinState(scenario_id=scenario_id, applied_label=candidate_id, simulated_minutes=360, stage_counts=sim["stage_counts"], patients=sim["patients"], event_log=event_log, resource_utilization=sim["resource_utilization"])

@app.get("/api/decisions", response_model=list[DecisionRecord])
def get_decisions(): return [DecisionRecord.model_validate(item) for item in list_decisions()]

@app.post("/api/decisions", response_model=DecisionRecord)
def create_decision(body: DecisionCreateRequest):
    record = DecisionRecord(id=f"decision-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}", scenario_id=body.scenario_id, question=body.question, recommendation=body.recommendation, impact=body.impact, created_at=datetime.now(timezone.utc).isoformat()); save_decision(record.model_dump(by_alias=True)); return record

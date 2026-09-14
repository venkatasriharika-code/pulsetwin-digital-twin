"""Two-speed decision engine: queueing shortlist followed by DES validation."""
from datetime import datetime, timezone
from app.data import WardConfig
from app.models import CandidateResult, ParsedScenario, Recommendation
from app.queueing import screen_configuration
from app.simulation import run_simulation

CANDIDATE_DELTAS = [
    {"id": "c1", "label": "+1 doctor", "doctors": 1},
    {"id": "c2", "label": "+2 doctors", "doctors": 2},
    {"id": "c3", "label": "+3 doctors", "doctors": 3},
    {"id": "c4", "label": "+2 doctors, +2 beds", "doctors": 2, "beds": 2},
    {"id": "c5", "label": "+1 nurse, +2 beds", "nurses": 1, "beds": 2},
    {"id": "c6", "label": "+2 doctors, +1 nurse", "doctors": 2, "nurses": 1},
]


def _score(avg_wait: float, critical_wait: float, utilization: float, doctors: int, nurses: int, beds: int, objective: str) -> float:
    critical_weight = 2.8 if objective == "protect_critical_wait" else 2.0
    cost = doctors * 4.0 + nurses * 1.5 + beds * 0.6
    return round(avg_wait * 0.4 + critical_wait * critical_weight + max(0.0, utilization - 85) * 0.8 + cost, 1)


def _candidate_from_sim(item: dict, sim: dict, score: float, is_recommended: bool, baseline: dict) -> CandidateResult:
    wait_delta = round(baseline["avg_wait_minutes"] - sim["avg_wait_minutes"], 1)
    tradeoff = f"{wait_delta:+.0f} min average wait; {sim['doctor_utilization_pct']:.0f}% doctor load"
    return CandidateResult(
        id=item["id"], label=item["label"], doctors_added=item.get("doctors", 0), nurses_added=item.get("nurses", 0), beds_added=item.get("beds", 0),
        avg_wait_minutes=sim["avg_wait_minutes"], critical_wait_minutes=sim["critical_wait_minutes"], serious_wait_minutes=sim["serious_wait_minutes"],
        throughput_per_hour=sim["throughput_per_hour"], doctor_utilization_pct=sim["doctor_utilization_pct"], bed_utilization_pct=sim["bed_utilization_pct"],
        score=score, fast_screen_score=item["fast_score"], is_recommended=is_recommended, tradeoff=tradeoff,
    )


def evaluate(scenario: ParsedScenario, base: WardConfig):
    configured_arrivals = scenario.arrivals_per_hour if scenario.arrivals_per_hour is not None else base.arrivals_per_hour
    configured_doctors = scenario.doctors if scenario.doctors is not None else base.doctors
    configured_nurses = scenario.nurses if scenario.nurses is not None else base.nurses
    configured_beds = scenario.beds if scenario.beds is not None else base.beds
    arrivals = configured_arrivals * (1 + scenario.arrival_surge_pct / 100)
    base_fast = screen_configuration(arrivals, configured_doctors, base.minutes_per_patient_doctor, base.severity_mix["critical"])
    base_sim = run_simulation(arrivals, configured_doctors, configured_nurses, configured_beds, base.severity_mix, seed=81)
    baseline_score = _score(base_sim["avg_wait_minutes"], base_sim["critical_wait_minutes"], base_sim["doctor_utilization_pct"], 0, 0, 0, scenario.objective)
    baseline_item = {"id": "baseline", "label": "Current staffing", "fast_score": baseline_score}
    baseline = _candidate_from_sim(baseline_item, base_sim, baseline_score, False, base_sim)

    screened = []
    for item in CANDIDATE_DELTAS:
        fast = screen_configuration(arrivals, configured_doctors + item.get("doctors", 0), base.minutes_per_patient_doctor, base.severity_mix["critical"])
        item = {**item, **fast}
        item["fast_score"] = _score(fast["avg_wait_minutes"], fast["critical_wait_minutes"], fast["doctor_utilization_pct"], item.get("doctors", 0), item.get("nurses", 0), item.get("beds", 0), scenario.objective)
        screened.append(item)
    shortlist = sorted(screened, key=lambda item: item["fast_score"])[:4]

    candidates = []
    sim_cache = {}
    for index, item in enumerate(shortlist):
        sim = run_simulation(arrivals, configured_doctors + item.get("doctors", 0), configured_nurses + item.get("nurses", 0), configured_beds + item.get("beds", 0), base.severity_mix, seed=100 + index)
        sim_cache[item["id"]] = sim
        score = _score(sim["avg_wait_minutes"], sim["critical_wait_minutes"], sim["doctor_utilization_pct"], item.get("doctors", 0), item.get("nurses", 0), item.get("beds", 0), scenario.objective)
        candidates.append(_candidate_from_sim(item, sim, score, False, base_sim))

    best = min(candidates, key=lambda candidate: candidate.score)
    for candidate in candidates:
        candidate.is_recommended = candidate.id == best.id
    impact = {
        "avgWaitReduction": round(baseline.avg_wait_minutes - best.avg_wait_minutes, 1),
        "criticalWaitReduction": round(baseline.critical_wait_minutes - best.critical_wait_minutes, 1),
        "throughputGain": round(best.throughput_per_hour - baseline.throughput_per_hour, 1),
        "utilizationChange": round(best.doctor_utilization_pct - baseline.doctor_utilization_pct, 1),
    }
    recommendation = Recommendation(
        summary=f"Recommend {best.label} for the {scenario.time_period}.",
        reasoning=f"The {scenario.arrival_surge_pct:.0f}% surge makes doctor capacity the binding constraint. The recommended configuration lowers average wait by {max(0, impact['avgWaitReduction']):.0f} minutes and protects high-acuity flow without paying for the highest-cost option.",
        why_now=f"Projected demand is {arrivals:.0f} patients/hour versus {configured_arrivals:.0f} now; current doctor utilization is estimated at {baseline.doctor_utilization_pct:.0f}%.",
        impact=impact,
        guardrails=["Validate against live staffing availability before execution.", "Re-check bed occupancy if the serious-patient mix rises above 40%.", "This synthetic twin is decision support, not a clinical protocol."],
    )
    return baseline, candidates, recommendation, sim_cache

"""Small deterministic discrete-event simulation for the hackathon twin."""

import heapq
import random
from dataclasses import dataclass, field
from app.models import ALL_STAGES, PipelineStage, Severity


@dataclass(order=True)
class _Event:
    time: float
    seq: int
    kind: str = field(compare=False)
    patient_id: str = field(compare=False)


@dataclass
class _Patient:
    id: str
    severity: Severity
    arrival_time: float
    stage: PipelineStage = "ARRIVED"
    wait_minutes: float = 0


def _sample_severity(rng: random.Random, mix: dict) -> Severity:
    roll = rng.random()
    cumulative = 0.0
    for severity, share in mix.items():
        cumulative += share
        if roll <= cumulative:
            return severity  # type: ignore[return-value]
    return "mild"


def run_simulation(
    arrivals_per_hour: float,
    doctors: int,
    nurses: int,
    beds: int,
    severity_mix: dict,
    sim_hours: float = 6.0,
    seed: int = 42,
) -> dict:
    rng = random.Random(seed)
    events: list[_Event] = []
    seq = 0

    def push(time: float, kind: str, patient_id: str):
        nonlocal seq
        seq += 1
        heapq.heappush(events, _Event(time, seq, kind, patient_id))

    patients: dict[str, _Patient] = {}
    doctor_free_at = [0.0] * max(doctors, 1)
    bed_free_at = [0.0] * max(beds, 1)
    waits: dict[str, list[float]] = {"critical": [], "serious": [], "mild": []}
    total_doctor_busy = 0.0
    total_bed_busy = 0.0
    arrivals = 0
    mean_gap = 60.0 / arrivals_per_hour if arrivals_per_hour > 0 else 999.0
    t = 0.0
    while t < sim_hours * 60:
        t += rng.expovariate(1.0 / mean_gap)
        if t >= sim_hours * 60:
            break
        arrivals += 1
        pid = f"P{100 + arrivals}"
        patients[pid] = _Patient(pid, _sample_severity(rng, severity_mix), t)
        push(t, "ARRIVE", pid)

    snapshot_time = sim_hours * 60
    while events and events[0].time <= snapshot_time:
        event = heapq.heappop(events)
        patient = patients[event.patient_id]
        if event.kind == "ARRIVE":
            patient.stage = "TRIAGE"
            push(event.time + rng.uniform(3, 8), "TRIAGE_DONE", patient.id)
        elif event.kind == "TRIAGE_DONE":
            patient.stage = "WAITING_FOR_DOCTOR"
            idx = min(range(len(doctor_free_at)), key=lambda i: doctor_free_at[i])
            start = max(event.time, doctor_free_at[idx])
            patient.wait_minutes = start - event.time
            waits[patient.severity].append(patient.wait_minutes)
            service = max(3.0, rng.gauss(11.0, 3.0))
            doctor_free_at[idx] = start + service
            total_doctor_busy += service
            push(start, "DOCTOR_START", patient.id)
            push(start + service, "DOCTOR_DONE", patient.id)
        elif event.kind == "DOCTOR_START":
            patient.stage = "DOCTOR"
        elif event.kind == "DOCTOR_DONE":
            if rng.random() < 0.62:
                patient.stage = "TESTING"
                push(event.time + rng.uniform(10, 25), "TEST_DONE", patient.id)
            else:
                patient.stage = "TREATMENT"
                push(event.time + rng.uniform(10, 30), "TREATMENT_DONE", patient.id)
        elif event.kind == "TEST_DONE":
            patient.stage = "TREATMENT"
            push(event.time + rng.uniform(10, 30), "TREATMENT_DONE", patient.id)
        elif event.kind == "TREATMENT_DONE":
            if patient.severity in ("critical", "serious") and rng.random() < 0.55:
                patient.stage = "WAITING_FOR_BED"
                idx = min(range(len(bed_free_at)), key=lambda i: bed_free_at[i])
                start = max(event.time, bed_free_at[idx])
                stay = rng.uniform(60, 240)
                bed_free_at[idx] = start + stay
                total_bed_busy += stay
                push(start, "BED_START", patient.id)
                push(start + stay, "DISCHARGE", patient.id)
            else:
                patient.stage = "DISCHARGED"
        elif event.kind == "BED_START":
            patient.stage = "BED"
        elif event.kind == "DISCHARGE":
            patient.stage = "DISCHARGED"

    def avg(values: list[float], fallback: float = 0.0) -> float:
        return round(sum(values) / len(values), 1) if values else fallback

    stage_counts = {stage: 0 for stage in ALL_STAGES}
    for patient in patients.values():
        stage_counts[patient.stage] += 1
    doctor_util = min(100.0, round(100 * total_doctor_busy / (max(doctors, 1) * snapshot_time), 1))
    bed_util = min(100.0, round(100 * total_bed_busy / (max(beds, 1) * snapshot_time), 1))
    return {
        "avg_wait_minutes": avg(waits["critical"] + waits["serious"] + waits["mild"]),
        "critical_wait_minutes": avg(waits["critical"], 0.0),
        "serious_wait_minutes": avg(waits["serious"], 0.0),
        "doctor_utilization_pct": doctor_util,
        "bed_utilization_pct": bed_util,
        "throughput_per_hour": round(stage_counts["DISCHARGED"] / sim_hours, 1),
        "queue_length": stage_counts["WAITING_FOR_DOCTOR"] + stage_counts["WAITING_FOR_BED"],
        "stage_counts": stage_counts,
        "patients": [
            {"id": p.id, "severity": p.severity, "stage": p.stage, "wait_minutes": round(p.wait_minutes, 1)}
            for p in list(patients.values())[-48:]
        ],
        "resource_utilization": {"doctors": doctor_util, "beds": bed_util, "nurses": min(100.0, round(doctor_util * 0.88, 1))},
    }

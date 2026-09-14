from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from app.models import ALL_STAGES, PipelineStage, Severity
from app.anomaly import AnomalyDetector

@dataclass
class Patient:
    id: str
    severity: Severity
    stage: PipelineStage = "ARRIVED"
    entered_at: float = 0.0
    wait_minutes: float = 0.0
    service_remaining: float = 0.0
    bed_remaining: float = 0.0

class LiveEmergencySimulation:
    """Small deterministic real-time ED engine. One call to tick advances virtual time."""
    def __init__(self, config, seed: int = 42, demand_multiplier: float = 1.0):
        self.config = config; self.rng = random.Random(seed); self.demand_multiplier = demand_multiplier
        self.clock = 0.0; self.seq = 0; self.patients: dict[str, Patient] = {}; self.doctor_slots: list[str | None] = [None] * max(config.doctors, 1); self.bed_slots: list[str | None] = [None] * max(config.beds, 1)
        self.total_arrivals = 0; self.total_discharged = 0; self.doctor_busy_minutes = 0.0; self.bed_busy_minutes = 0.0; self.events: list[str] = []; self.anomaly_detector = AnomalyDetector(config.arrivals_per_hour, config.doctors, config.beds)

    def _severity(self) -> Severity:
        roll = self.rng.random(); cursor = 0.0
        for key in ("critical", "serious", "mild"):
            cursor += self.config.severity_mix.get(key, 0)
            if roll <= cursor: return key  # type: ignore[return-value]
        return "mild"

    def _new_patient(self) -> Patient:
        self.total_arrivals += 1; pid = f"P{1000 + self.total_arrivals}"; patient = Patient(pid, self._severity(), "ARRIVED", self.clock); self.patients[pid] = patient; return patient

    def _priority(self, p: Patient) -> tuple[int, float]:
        return ({"critical": 0, "serious": 1, "mild": 2}[p.severity], p.entered_at)

    def _queue(self, stage: PipelineStage) -> list[Patient]:
        return sorted([p for p in self.patients.values() if p.stage == stage], key=self._priority)

    def _start_doctors(self):
        for idx, current in enumerate(self.doctor_slots):
            if current is None:
                queue = self._queue("WAITING_FOR_DOCTOR")
                if queue:
                    p = queue[0]; p.stage = "DOCTOR"; p.service_remaining = max(4.0, self.rng.gauss(self.config.minutes_per_patient_doctor, 2.5)); self.doctor_slots[idx] = p.id; self.events.append(f"{self._stamp()} · {p.id} assigned to doctor")

    def _start_beds(self):
        for idx, current in enumerate(self.bed_slots):
            if current is None:
                queue = self._queue("WAITING_FOR_BED")
                if queue:
                    p = queue[0]; p.stage = "BED"; p.bed_remaining = self.rng.uniform(60, 240); self.bed_slots[idx] = p.id; self.events.append(f"{self._stamp()} · {p.id} assigned inpatient bed")

    def _stamp(self) -> str:
        return f"{int(self.clock // 60):02d}:{int(self.clock % 60):02d}"

    def tick(self, minutes: float = 5.0) -> dict[str, Any]:
        end = self.clock + minutes
        # Poisson-like arrivals, with a fractional accumulator represented by a probability per tick.
        expected = self.config.arrivals_per_hour * self.demand_multiplier * minutes / 60
        arrivals = int(expected); arrivals += int(self.rng.random() < (expected - arrivals))
        for _ in range(arrivals):
            p = self._new_patient(); p.stage = "TRIAGE"; p.service_remaining = self.rng.uniform(3, 8); self.events.append(f"{self._stamp()} · {p.id} arrived ({p.severity})")
        for p in list(self.patients.values()):
            if p.stage in ("WAITING_FOR_DOCTOR", "WAITING_FOR_BED", "TRIAGE"): p.wait_minutes += minutes
            if p.stage == "TRIAGE":
                p.service_remaining -= minutes
                if p.service_remaining <= 0: p.stage = "WAITING_FOR_DOCTOR"; self.events.append(f"{self._stamp()} · {p.id} cleared triage")
            elif p.stage == "DOCTOR":
                self.doctor_busy_minutes += minutes; p.service_remaining -= minutes
                if p.service_remaining <= 0:
                    for idx, pid in enumerate(self.doctor_slots):
                        if pid == p.id: self.doctor_slots[idx] = None
                    if self.rng.random() < .62: p.stage = "TESTING"; p.service_remaining = self.rng.uniform(10, 25)
                    else: p.stage = "TREATMENT"; p.service_remaining = self.rng.uniform(10, 30)
            elif p.stage in ("TESTING", "TREATMENT"):
                p.service_remaining -= minutes
                if p.service_remaining <= 0:
                    if p.severity in ("critical", "serious") and self.rng.random() < .55: p.stage = "WAITING_FOR_BED"
                    else: p.stage = "DISCHARGED"; self.total_discharged += 1; self.events.append(f"{self._stamp()} · {p.id} discharged")
            elif p.stage == "BED":
                self.bed_busy_minutes += minutes; p.bed_remaining -= minutes
                if p.bed_remaining <= 0:
                    for idx, pid in enumerate(self.bed_slots):
                        if pid == p.id: self.bed_slots[idx] = None
                    p.stage = "DISCHARGED"; self.total_discharged += 1; self.events.append(f"{self._stamp()} · {p.id} discharged from bed")
        self._start_doctors(); self._start_beds(); self.clock = end
        snapshot = self.snapshot(); snapshot["anomaly"] = self.anomaly_detector.update(snapshot); return snapshot

    def snapshot(self) -> dict[str, Any]:
        counts = {stage: 0 for stage in ALL_STAGES}
        for p in self.patients.values(): counts[p.stage] += 1
        active_hours = max(self.clock / 60, 1/60); doctor_util = min(100, round(self.doctor_busy_minutes / (max(self.config.doctors, 1) * max(self.clock, 1)) * 100, 1)); bed_util = min(100, round(self.bed_busy_minutes / (max(self.config.beds, 1) * max(self.clock, 1)) * 100, 1)); waiting = self._queue("WAITING_FOR_DOCTOR") + self._queue("WAITING_FOR_BED")
        return {"simulatedMinutes": round(self.clock), "stageCounts": counts, "patients":[{"id":p.id,"severity":p.severity,"stage":p.stage,"waitMinutes":round(p.wait_minutes,1)} for p in list(self.patients.values())[-48:]], "resourceUtilization":{"doctors":doctor_util,"beds":bed_util,"nurses":min(100,round(doctor_util*.88,1))}, "queueMetrics":{"queueLength":len(waiting),"doctorQueue":counts["WAITING_FOR_DOCTOR"],"bedQueue":counts["WAITING_FOR_BED"],"avgWaitMinutes":round(sum(p.wait_minutes for p in waiting)/len(waiting),1) if waiting else 0,"throughputPerHour":round(self.total_discharged/active_hours,1),"arrivals":self.total_arrivals,"discharged":self.total_discharged}, "eventLog":self.events[-25:]}

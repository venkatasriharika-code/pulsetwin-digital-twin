from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


Severity = Literal["critical", "serious", "mild"]
PipelineStage = Literal[
    "ARRIVED", "TRIAGE", "WAITING_FOR_DOCTOR", "DOCTOR", "TESTING",
    "TREATMENT", "WAITING_FOR_BED", "BED", "DISCHARGED"
]
ALL_STAGES: list[PipelineStage] = [
    "ARRIVED", "TRIAGE", "WAITING_FOR_DOCTOR", "DOCTOR", "TESTING",
    "TREATMENT", "WAITING_FOR_BED", "BED", "DISCHARGED"
]


class ResourceStatus(CamelModel):
    name: str
    used: int
    total: int
    utilization_pct: float
    status: Literal["healthy", "watch", "strained"]


class TrendPoint(CamelModel):
    label: str
    arrivals: int
    wait_minutes: float
    utilization_pct: float


class WardStatus(CamelModel):
    timestamp: str
    arrivals_per_hour: float
    patients_in_system: int
    doctors: int
    nurses: int
    beds: int
    beds_available: int
    avg_wait_minutes: float
    critical_wait_minutes: float
    serious_wait_minutes: float
    staff_utilization_pct: float
    throughput_per_hour: float
    queue_length: int
    acuity_mix: dict[str, float]
    resources: list[ResourceStatus]
    trend: list[TrendPoint]
    alerts: list[str]


class HospitalConfig(CamelModel):
    arrivals_per_hour: float = Field(ge=0, le=200)
    doctors: int = Field(ge=0, le=50)
    nurses: int = Field(ge=0, le=80)
    beds: int = Field(ge=0, le=200)
    triage_nurses: int = Field(ge=0, le=20)
    ct_capacity: int = Field(ge=0, le=10)
    lab_capacity: int = Field(ge=0, le=20)
    minutes_per_patient_doctor: float = Field(gt=0, le=120)
    severity_mix: dict[str, float]
    updated_at: Optional[str] = None


class HospitalConfigUpdate(CamelModel):
    arrivals_per_hour: float = Field(ge=0, le=200)
    doctors: int = Field(ge=0, le=50)
    nurses: int = Field(ge=0, le=80)
    beds: int = Field(ge=0, le=200)
    triage_nurses: int = Field(ge=0, le=20)
    ct_capacity: int = Field(ge=0, le=10)
    lab_capacity: int = Field(ge=0, le=20)
    minutes_per_patient_doctor: float = Field(gt=0, le=120)
    severity_mix: dict[str, float]


class ScenarioParseRequest(CamelModel):
    question: str


class ParsedScenario(CamelModel):
    id: str
    raw_question: str
    arrival_surge_pct: float = Field(ge=0, le=200)
    time_period: str
    objective: str
    arrivals_per_hour: Optional[float] = Field(default=None, ge=0, le=200)
    doctors: Optional[int] = Field(default=None, ge=0, le=50)
    nurses: Optional[int] = Field(default=None, ge=0, le=80)
    beds: Optional[int] = Field(default=None, ge=0, le=200)
    triage_nurses: Optional[int] = Field(default=None, ge=0, le=20)
    ct_capacity: Optional[int] = Field(default=None, ge=0, le=10)
    lab_capacity: Optional[int] = Field(default=None, ge=0, le=20)
    extra_doctors: Optional[int] = Field(default=None, ge=0, le=10)
    extra_nurses: Optional[int] = Field(default=None, ge=0, le=10)
    extra_beds: Optional[int] = Field(default=None, ge=0, le=30)


class ScenarioEvaluateRequest(CamelModel):
    scenario: ParsedScenario


class CandidateResult(CamelModel):
    id: str
    label: str
    doctors_added: int = 0
    nurses_added: int = 0
    beds_added: int = 0
    avg_wait_minutes: float
    critical_wait_minutes: float
    serious_wait_minutes: float
    throughput_per_hour: float
    doctor_utilization_pct: float
    bed_utilization_pct: float
    score: float
    fast_screen_score: float
    is_recommended: bool
    tradeoff: str


class Recommendation(CamelModel):
    summary: str
    reasoning: str
    why_now: str
    impact: dict[str, float]
    guardrails: list[str]


class EvaluationResult(CamelModel):
    scenario: ParsedScenario
    baseline: CandidateResult
    candidates: list[CandidateResult]
    recommendation: Recommendation
    pipeline: list[str]
    computed_at: str


class DecisionRecord(CamelModel):
    id: str
    scenario_id: str
    question: str
    recommendation: str
    impact: dict[str, float]
    created_at: str


class WardPatient(CamelModel):
    id: str
    severity: Severity
    stage: PipelineStage
    wait_minutes: float = 0


class WardTwinState(CamelModel):
    scenario_id: str
    applied_label: str
    simulated_minutes: int
    stage_counts: dict[str, int]
    patients: list[WardPatient]
    event_log: list[str]
    resource_utilization: dict[str, float]


class DecisionCreateRequest(CamelModel):
    scenario_id: str
    question: str
    recommendation: str
    impact: dict[str, float]


class ModelTrainRequest(CamelModel):
    seed: int = 42


class ModelPredictRequest(CamelModel):
    ed_volume: float = Field(ge=1, le=4)
    left_before_seen_pct: float = Field(ge=0, le=100)
    head_ct_score: float = Field(ge=0, le=100)


class RecommendationGenerateRequest(CamelModel):
    snapshot: Optional[dict] = None
    surge_probability: Optional[float] = Field(default=None, ge=0, le=1)

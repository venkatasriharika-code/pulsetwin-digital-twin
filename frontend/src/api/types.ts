export type Severity = "critical" | "serious" | "mild";

export interface ResourceStatus { name: string; used: number; total: number; utilizationPct: number; status: "healthy" | "watch" | "strained"; }
export interface TrendPoint { label: string; arrivals: number; waitMinutes: number; utilizationPct: number; }
export interface WardStatus {
  timestamp: string; arrivalsPerHour: number; patientsInSystem: number; doctors: number; nurses: number; beds: number; bedsAvailable: number;
  avgWaitMinutes: number; criticalWaitMinutes: number; seriousWaitMinutes: number; staffUtilizationPct: number; throughputPerHour: number; queueLength: number;
  acuityMix: Record<string, number>; resources: ResourceStatus[]; trend: TrendPoint[]; alerts: string[];
}
export interface HospitalConfig {
  arrivalsPerHour: number; doctors: number; nurses: number; beds: number; triageNurses: number;
  ctCapacity: number; labCapacity: number; minutesPerPatientDoctor: number;
  severityMix: { critical: number; serious: number; mild: number }; updatedAt?: string;
}
export interface ParsedScenario {
  id: string;
  rawQuestion: string;
  arrivalSurgePct: number;
  timePeriod: string;
  objective: string;
  arrivalsPerHour?: number;
  doctors?: number;
  nurses?: number;
  beds?: number;
  triageNurses?: number;
  ctCapacity?: number;
  labCapacity?: number;
  extraDoctors?: number;
  extraNurses?: number;
  extraBeds?: number;
}
export interface CandidateResult {
  id: string; label: string; doctorsAdded: number; nursesAdded: number; bedsAdded: number; avgWaitMinutes: number; criticalWaitMinutes: number; seriousWaitMinutes: number;
  throughputPerHour: number; doctorUtilizationPct: number; bedUtilizationPct: number; score: number; fastScreenScore: number; isRecommended: boolean; tradeoff: string;
}
export interface EvaluationResult {
  scenario: ParsedScenario; baseline: CandidateResult; candidates: CandidateResult[];
  recommendation: { summary: string; reasoning: string; whyNow: string; impact: Record<string, number>; guardrails: string[] };
  pipeline: string[]; computedAt: string;
}
export interface DecisionRecord { id: string; scenarioId: string; question: string; recommendation: string; impact: Record<string, number>; createdAt: string; }
export type PipelineStage = "ARRIVED" | "TRIAGE" | "WAITING_FOR_DOCTOR" | "DOCTOR" | "TESTING" | "TREATMENT" | "WAITING_FOR_BED" | "BED" | "DISCHARGED";
export interface WardPatient { id: string; severity: Severity; stage: PipelineStage; waitMinutes: number; }
export interface WardTwinState { scenarioId: string; appliedLabel: string; simulatedMinutes: number; stageCounts: Record<PipelineStage, number>; patients: WardPatient[]; eventLog: string[]; resourceUtilization: Record<string, number>; }
export interface LiveSimulationSnapshot { simulatedMinutes: number; stageCounts: Record<PipelineStage, number>; patients: WardPatient[]; eventLog: string[]; resourceUtilization: Record<string, number>; queueMetrics: { queueLength: number; doctorQueue: number; bedQueue: number; avgWaitMinutes: number; throughputPerHour: number; arrivals: number; discharged: number }; anomaly?: { alerts: AlertRecord[]; surgeProbability: number; signals: string[]; isAnomalous: boolean }; }
export interface AlertRecord { id: string; type: string; level: "warning" | "critical"; title: string; message: string; predictedSurgeProbability: number; simulatedMinutes: number; createdAt: string; recommendedAction: string; }
export interface ResourceRecommendation { id: string; status: "proposed" | "applied"; createdAt: string; appliedAt?: string; surgeProbability: number; summary: string; rationale: string; trigger: { queueLength: number; doctorUtilizationPct: number; bedUtilizationPct: number; arrivalRatio: number }; resourceActions: Array<{ from: string; to: string; role: string; count: number; reason: string }>; shiftRecommendations: Array<{ label: string; start: string; end: string; additionalDoctors: number; additionalNurses: number; additionalBeds: number; confidence: number }>; guardrails: string[]; }
export interface ModelStatus { status: string; modelVersion?: string; dataset?: { name: string; source: string; rows: number; features: string[]; target: string }; trainedRows?: number; testRows?: number; waitTime?: { maeMinutes: number; rmseMinutes: number; r2: number }; bottleneck?: { thresholdMinutes: number; accuracy: number; balancedAccuracy: number; precision: number; recall: number; f1: number }; message?: string; }
export interface ModelPrediction { predictedWaitMinutes: number; bottleneckRisk: "high" | "normal"; modelVersion?: string; }

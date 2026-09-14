import type { WardStatus, ParsedScenario, EvaluationResult, WardTwinState, DecisionRecord, HospitalConfig, ModelStatus, ModelPrediction, AlertRecord, ResourceRecommendation } from "./types";
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
export class ApiError extends Error { status?: number; constructor(message: string, status?: number) { super(message); this.status = status; } }
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let res: Response;
  try { res = await fetch(`${BASE_URL}${path}`, { headers: { "Content-Type": "application/json" }, ...options }); }
  catch { throw new ApiError("Could not reach the PulseTwin backend. Check that the API server is running."); }
  if (!res.ok) { const body = await res.json().catch(() => null); throw new ApiError(body?.detail ?? body?.message ?? `Request failed (${res.status})`, res.status); }
  return res.json() as Promise<T>;
}
export const api = {
  getWardStatus: () => request<WardStatus>("/api/status"),
  parseScenario: (question: string) => request<ParsedScenario>("/api/scenario/parse", { method: "POST", body: JSON.stringify({ question }) }),
  evaluateScenario: (scenario: ParsedScenario) => request<EvaluationResult>("/api/scenario/evaluate", { method: "POST", body: JSON.stringify({ scenario }) }),
  getWardTwinState: (scenarioId: string, candidateId: string) => request<WardTwinState>(`/api/ward/state?scenarioId=${encodeURIComponent(scenarioId)}&candidateId=${encodeURIComponent(candidateId)}`),
  getDecisions: () => request<DecisionRecord[]>("/api/decisions"),
  createDecision: (payload: { scenarioId: string; question: string; recommendation: string; impact: Record<string, number> }) => request<DecisionRecord>("/api/decisions", { method: "POST", body: JSON.stringify(payload) }),
  getConfig: () => request<HospitalConfig>("/api/config"),
  updateConfig: (config: HospitalConfig) => request<HospitalConfig>("/api/config", { method: "PUT", body: JSON.stringify(config) }),
  getModelStatus: () => request<ModelStatus>("/api/ml/status"),
  trainModels: (seed = 42) => request<ModelStatus>("/api/ml/train", { method: "POST", body: JSON.stringify({ seed }) }),
  predictOperations: (features: { edVolume: number; leftBeforeSeenPct: number; headCtScore: number }) => request<ModelPrediction>("/api/ml/predict", { method: "POST", body: JSON.stringify(features) }),
  getAlerts: () => request<AlertRecord[]>("/api/alerts"),
  getRecommendations: () => request<ResourceRecommendation[]>("/api/recommendations"),
  generateRecommendation: (snapshot?: unknown, surgeProbability?: number) => request<ResourceRecommendation>("/api/recommendations/generate", { method: "POST", body: JSON.stringify({ snapshot, surgeProbability }) }),
  applyRecommendation: (id: string) => request<{ recommendation: ResourceRecommendation; config: HospitalConfig }>(`/api/recommendations/${id}/apply`, { method: "POST" }),
};

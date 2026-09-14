from __future__ import annotations

import math
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any

class AnomalyDetector:
    def __init__(self, baseline_arrivals: float, doctors: int, beds: int):
        self.baseline_arrivals = max(baseline_arrivals, 1); self.doctors = max(doctors, 1); self.beds = max(beds, 1); self.arrival_history: deque[float] = deque(maxlen=12); self.queue_history: deque[float] = deque(maxlen=12); self.util_history: deque[float] = deque(maxlen=12)

    def _z(self, value: float, history: deque[float]) -> float:
        if len(history) < 3: return 0.0
        mean = sum(history) / len(history); std = math.sqrt(sum((x - mean) ** 2 for x in history) / len(history)) or 1.0
        return (value - mean) / std

    def update(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        metrics = snapshot["queueMetrics"]; arrivals_rate = metrics["arrivals"] / max(snapshot["simulatedMinutes"] / 60, 1/60); queue = float(metrics["queueLength"]); doctor_util = float(snapshot["resourceUtilization"].get("doctors", 0));
        signals: list[str] = []; alerts: list[dict[str, Any]] = []
        arrival_ratio = arrivals_rate / self.baseline_arrivals
        surge_probability = min(0.99, max(0.01, 0.12 + max(0, arrival_ratio - 1) * .7 + max(0, doctor_util - 80) / 100 * .25 + max(0, queue - 4) / 30))
        if arrival_ratio >= 1.35: signals.append(f"arrival rate {arrivals_rate:.1f}/hr is {arrival_ratio:.1f}× baseline")
        if queue >= max(6, self.doctors * 1.5): signals.append(f"priority queues hold {int(queue)} patients")
        if doctor_util >= 90: signals.append(f"doctor utilization is {doctor_util:.0f}%")
        if signals:
            level = "critical" if doctor_util >= 95 or queue >= self.doctors * 3 else "warning"
            alerts.append({"id":f"alert-{uuid.uuid4().hex[:10]}","type":"ed-surge","level":level,"title":"Emergency department surge risk","message":"; ".join(signals),"predictedSurgeProbability":round(surge_probability,2),"simulatedMinutes":snapshot["simulatedMinutes"],"createdAt":datetime.now(timezone.utc).isoformat(),"recommendedAction":"Open surge capacity and review next-shift staffing."})
        if self._z(queue, self.queue_history) >= 2.0:
            alerts.append({"id":f"alert-{uuid.uuid4().hex[:10]}","type":"queue-anomaly","level":"warning","title":"Queue growth anomaly","message":f"Queue length {int(queue)} is statistically above its recent operating range.","predictedSurgeProbability":round(surge_probability,2),"simulatedMinutes":snapshot["simulatedMinutes"],"createdAt":datetime.now(timezone.utc).isoformat(),"recommendedAction":"Prioritize doctor allocation and bed turnover."})
        self.arrival_history.append(arrivals_rate); self.queue_history.append(queue); self.util_history.append(doctor_util)
        return {"alerts": alerts, "surgeProbability": round(surge_probability, 2), "signals": signals, "isAnomalous": bool(alerts)}

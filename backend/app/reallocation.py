from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from app.db import new_id


def generate_recommendation(config, snapshot: dict[str, Any] | None = None, surge_probability: float | None = None) -> dict[str, Any]:
    metrics = (snapshot or {}).get("queueMetrics", {}); resources = (snapshot or {}).get("resourceUtilization", {}); anomaly = (snapshot or {}).get("anomaly", {})
    probability = float(surge_probability if surge_probability is not None else anomaly.get("surgeProbability", .12)); queue = int(metrics.get("queueLength", round(config.arrivals_per_hour * .38))); doctor_util = float(resources.get("doctors", 0)); bed_util = float(resources.get("beds", 72)); arrival_ratio = max(1.0, probability / .12)
    extra_doctors = max(0, min(4, round((probability * 3) + max(0, queue - config.doctors) / 5))) if probability >= .45 or queue >= config.doctors * 1.5 else 0
    extra_nurses = max(0, min(6, round(extra_doctors * 1.5 + (1 if probability >= .7 else 0))))
    extra_beds = max(0, min(10, round((queue * .35) + (2 if probability >= .7 else 0)))) if probability >= .45 or bed_util >= 85 else 0
    redeploy = []
    if extra_doctors: redeploy.append({"from":"scheduled elective coverage","to":"emergency department","role":"doctor","count":extra_doctors,"reason":"protect critical and serious patient response time"})
    if extra_nurses: redeploy.append({"from":"low-acuity observation","to":"triage and treatment","role":"nurse","count":extra_nurses,"reason":"increase front-door throughput and reassessment capacity"})
    shifts = []
    for label, start, end, multiplier in [("Current shift","now","+4h",1.0),("Next shift","+4h","+12h",.9),("Following shift","+12h","+20h",.65)]:
        d = max(0, round(extra_doctors * multiplier)); n = max(0, round(extra_nurses * multiplier)); shifts.append({"label":label,"start":start,"end":end,"additionalDoctors":d,"additionalNurses":n,"additionalBeds":max(0, round(extra_beds * multiplier)),"confidence":round(max(.35, probability * (1 if multiplier == 1 else .85)),2)})
    actions = []
    if extra_doctors: actions.append(f"Reallocate {extra_doctors} doctor(s) to ED coverage")
    if extra_nurses: actions.append(f"Move {extra_nurses} nurse(s) into triage/treatment")
    if extra_beds: actions.append(f"Open {extra_beds} surge bed(s) and accelerate discharge rounds")
    if not actions: actions.append("Maintain current roster and continue monitoring the next simulation ticks")
    return {"id":new_id("rec"),"status":"proposed","createdAt":datetime.now(timezone.utc).isoformat(),"surgeProbability":round(probability,2),"trigger":{"queueLength":queue,"doctorUtilizationPct":doctor_util,"bedUtilizationPct":bed_util,"arrivalRatio":round(arrival_ratio,2)},"resourceActions":redeploy,"shiftRecommendations":shifts,"summary":"; ".join(actions),"rationale":"Recommendation combines predicted surge probability with queue pressure and resource utilization. It is a planning proposal, not an automatic clinical order.","guardrails":["Confirm staff availability and credentialing before assignment","Do not reallocate critical-care coverage without charge-nurse approval","Review again after the next live simulation tick"]}

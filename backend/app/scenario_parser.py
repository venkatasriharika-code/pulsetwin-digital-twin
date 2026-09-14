"""Converts a manager's natural-language question into structured scenario
parameters. This is a lightweight rule-based parser so the backend runs with
zero external dependencies. Swap this out for an LLM call (extracting the
same JSON shape) if you want more flexible language understanding — see the
architecture note in README.md."""

import re
import uuid

from app.models import ParsedScenario


def parse_question(question: str) -> ParsedScenario:
    text = question.lower()

    surge_match = re.search(r"(\d+)\s*%", text)
    arrival_surge_pct = float(surge_match.group(1)) if surge_match else 20.0

    if "night" in text:
        time_period = "night shift"
    elif "weekend" in text:
        time_period = "weekend"
    elif "morning" in text:
        time_period = "morning shift"
    else:
        time_period = "next 24h"

    if "critical" in text or "acuity" in text:
        objective = "protect_critical_wait"
    elif "cost" in text or "budget" in text:
        objective = "minimize_cost"
    else:
        objective = "minimize_waiting"

    doctors_match = re.search(r"(\d+)\s*(extra\s*|additional\s*)?doctors?", text)
    nurses_match = re.search(r"(\d+)\s*(extra\s*|additional\s*)?nurses?", text)
    beds_match = re.search(r"(\d+)\s*(extra\s*|additional\s*)?beds?", text)

    return ParsedScenario(
        id=str(uuid.uuid4()),
        raw_question=question,
        arrival_surge_pct=arrival_surge_pct,
        time_period=time_period,
        objective=objective,
        extra_doctors=int(doctors_match.group(1)) if doctors_match else None,
        extra_nurses=int(nurses_match.group(1)) if nurses_match else None,
        extra_beds=int(beds_match.group(1)) if beds_match else None,
    )

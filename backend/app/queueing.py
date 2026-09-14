"""Fast mathematical screening layer.

Models doctors as an M/M/c queue: patients = customers, doctors = servers.
This is deliberately cheap (no random sampling) so it can screen many
candidate staffing configurations before the slower simulation engine
validates the top few. See simulation.py for the detailed DES layer.
"""

import math


def erlang_c_wait_minutes(arrivals_per_hour: float, servers: int, minutes_per_service: float) -> float:
    """Expected wait time (minutes) in an M/M/c queue before a server is free.

    arrivals_per_hour: lambda, patient arrival rate
    servers: c, number of doctors
    minutes_per_service: 1/mu in minutes, average doctor time per patient
    """
    if servers <= 0:
        return float("inf")

    service_rate_per_hour = 60.0 / minutes_per_service  # mu, patients/hour/doctor
    offered_load = arrivals_per_hour / service_rate_per_hour  # a = lambda/mu (erlangs)
    utilization = offered_load / servers  # rho

    if utilization >= 1:
        # System is unstable at this staffing level — queue grows without bound.
        return float("inf")

    # Erlang-C probability of waiting (queueing formula), computed via the
    # standard recursive form to avoid overflow with large factorials.
    inv_erlang_b = 1.0
    for k in range(1, servers + 1):
        inv_erlang_b = 1.0 + (inv_erlang_b * k) / offered_load
    erlang_b = 1.0 / inv_erlang_b

    erlang_c = (servers * erlang_b) / (servers - offered_load * (1 - erlang_b))
    erlang_c = min(max(erlang_c, 0.0), 1.0)

    avg_wait_hours = erlang_c / (servers * service_rate_per_hour - arrivals_per_hour)
    return max(0.0, avg_wait_hours * 60.0)


def utilization_pct(arrivals_per_hour: float, servers: int, minutes_per_service: float) -> float:
    if servers <= 0:
        return 100.0
    service_rate_per_hour = 60.0 / minutes_per_service
    offered_load = arrivals_per_hour / service_rate_per_hour
    return min(100.0, round(100.0 * offered_load / servers, 1))


def screen_configuration(
    arrivals_per_hour: float,
    doctors: int,
    minutes_per_patient_doctor: float,
    critical_share: float,
) -> dict:
    """Fast estimate for one staffing configuration. Critical patients are
    assumed to be triaged ahead of the general queue, so their wait is
    approximated as a fraction of the overall queueing delay."""
    base_wait = erlang_c_wait_minutes(arrivals_per_hour, doctors, minutes_per_patient_doctor)
    # Triage priority discount: critical patients wait roughly 35% of the
    # general queueing delay, reflecting priority handling ahead of others.
    critical_wait = base_wait * 0.35 if math.isfinite(base_wait) else base_wait
    util = utilization_pct(arrivals_per_hour, doctors, minutes_per_patient_doctor)
    return {
        "avg_wait_minutes": round(base_wait, 1) if math.isfinite(base_wait) else 999.0,
        "critical_wait_minutes": round(critical_wait, 1) if math.isfinite(critical_wait) else 999.0,
        "doctor_utilization_pct": util,
    }

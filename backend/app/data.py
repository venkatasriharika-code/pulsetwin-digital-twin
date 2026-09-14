from dataclasses import dataclass


@dataclass
class WardConfig:
    arrivals_per_hour: float = 25.0
    doctors: int = 5
    nurses: int = 8
    beds: int = 20
    triage_nurses: int = 2
    ct_capacity: int = 1
    lab_capacity: int = 2
    minutes_per_patient_doctor: float = 11.0
    severity_mix: dict = None

    def __post_init__(self):
        if self.severity_mix is None:
            self.severity_mix = {"critical": 0.12, "serious": 0.38, "mild": 0.50}


BASE_CONFIG = WardConfig()

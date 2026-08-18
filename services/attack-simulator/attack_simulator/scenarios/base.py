from dataclasses import dataclass


@dataclass
class ScenarioResult:
    name: str
    requests_sent: int
    expected_risk_level: str
    expected_attack_type: str
    narrative: str

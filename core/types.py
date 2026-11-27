"""Shared result types. Every check returns a CheckResult with reason codes."""
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Finding:
    code: str          # machine-readable reason code, e.g. NAME_MISMATCH
    message: str       # human-readable explanation for the reviewer / auditor
    points: int = 0    # risk points this finding contributed (0 = informational)
    severity: str = "info"  # info | low | medium | high | critical


@dataclass
class CheckResult:
    key: str
    risk: int = 0
    findings: list = field(default_factory=list)
    details: dict = field(default_factory=dict)
    # Hard rule: if set, the final score can never be lower than this.
    floor: int = 0
    images: dict = field(default_factory=dict)  # name -> PNG bytes (not stored in JSON)

    def add(self, code, message, points=0, severity=None, floor=0):
        if severity is None:
            severity = ("info" if points == 0 else "low" if points < 20 else
                        "medium" if points < 40 else "high")
        self.findings.append(Finding(code, message, points, severity))
        self.risk = min(100, self.risk + points)
        self.floor = max(self.floor, floor)
        return self

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("images", None)
        return d

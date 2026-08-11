"""Shared data shapes for consistent API responses."""
import dataclasses
from datetime import datetime
from typing import Any, List, Optional


@dataclasses.dataclass
class ApiError:
    code: str
    message: str


@dataclasses.dataclass
class ApiResponse:
    success: bool
    data: Any = None
    error: Optional[ApiError] = None
    timestamp: str = dataclasses.field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": dataclasses.asdict(self.error) if self.error else None,
            "timestamp": self.timestamp,
        }


@dataclasses.dataclass
class HealthFactor:
    factor: str
    impact: int
    reason: str


@dataclasses.dataclass
class HealthResult:
    score: int
    status: str
    color: str
    factors: List[HealthFactor]
    issues: List[str]

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "status": self.status,
            "color": self.color,
            "factors": [dataclasses.asdict(f) for f in self.factors],
            "issues": self.issues,
        }


@dataclasses.dataclass
class SecurityFinding:
    pid: int
    name: str
    severity: str
    heuristic_strength: float
    score: int
    reasons: List[str]
    evidence: dict
    recommendation: str = ""

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class PortInfo:
    port: int
    protocol: str
    local_address: str
    pid: Optional[int]
    process_name: Optional[str]
    service: Optional[str]
    risk_level: str
    exposed: bool

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class Recommendation:
    severity: str
    title: str
    description: str
    action: str

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def status_for_score(score, critical=39, poor=59, fair=74, good=89):
    """Map a 0-100 score to a human label + color."""
    if score <= critical:
        return {"label": "Critical", "color": "red"}
    if score <= poor:
        return {"label": "Poor", "color": "orange"}
    if score <= fair:
        return {"label": "Fair", "color": "yellow"}
    if score <= good:
        return {"label": "Good", "color": "lightgreen"}
    return {"label": "Excellent", "color": "green"}

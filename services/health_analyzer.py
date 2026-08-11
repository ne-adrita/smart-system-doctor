"""Rule-based System Health Score.

Produces a transparent 0-100 score plus the individual factors that affected
it, so users can see exactly why a system scores the way it does.

Status bands:
    0-39   Critical
    40-59  Poor
    60-74  Fair
    75-89  Good
    90-100 Excellent
"""
from config import Config
from models.schemas import HealthFactor, HealthResult, status_for_score


def _impact(value, high, medium, high_penalty, medium_penalty):
    """Return (impact, reason) based on usage thresholds."""
    if value >= high:
        return high_penalty, f"usage is at {value:.1f}% (above {high:.0f}%)"
    if value >= medium:
        return medium_penalty, f"usage is at {value:.1f}% (above {medium:.0f}%)"
    return 0, f"usage is healthy at {value:.1f}%"


def compute_health_score(cpu, ram, disk, process_count=None, network=None):
    """Compute the health score with transparent factors."""
    factors = []
    issues = []

    impact, reason = _impact(cpu, Config.HEALTH_CPU_HIGH, Config.HEALTH_CPU_MEDIUM,
                             -30, -12)
    if impact:
        factors.append(HealthFactor("CPU", impact, f"CPU {reason}"))
    else:
        factors.append(HealthFactor("CPU", impact, f"CPU {reason}"))

    impact, reason = _impact(ram, Config.HEALTH_RAM_HIGH, Config.HEALTH_RAM_MEDIUM,
                             -30, -12)
    factors.append(HealthFactor("RAM", impact, f"RAM {reason}"))

    impact, reason = _impact(disk, Config.HEALTH_DISK_HIGH, Config.HEALTH_DISK_MEDIUM,
                             -20, -10)
    factors.append(HealthFactor("Disk", impact, f"Disk {reason}"))

    if process_count is not None and process_count > 500:
        penalty = -10
        factors.append(HealthFactor("Processes", penalty,
                                    f"High process count ({process_count})"))
    else:
        factors.append(HealthFactor("Processes", 0, "Process count is normal"))

    if network is not None:
        factors.append(HealthFactor("Network", 0, "Network activity is normal"))

    score = max(0, 100 + sum(f.impact for f in factors))
    status = status_for_score(score)
    if score <= 39:
        issues.append("System health is critical - immediate attention required")
    elif score <= 59:
        issues.append("System health is poor - performance may be degraded")
    elif score <= 74:
        issues.append("System health is fair - monitor resource usage")
    elif score <= 89:
        issues.append("System health is good")
    else:
        issues.append("System health is excellent")

    for f in factors:
        if f.impact < 0:
            issues.append(f"{f.factor} {f.reason}")

    return HealthResult(
        score=score,
        status=status["label"],
        color=status["color"],
        factors=factors,
        issues=issues,
    )

"""Rule-based System Health Score.

Produces a transparent 0-100 score plus the individual factors that affected
it, so users can see exactly why a system scores the way it does.

Penalties are *gradual* rather than step-like: usage is compared against a
low threshold and the penalty grows continuously with usage (capped), so a
reading of 79.9% and 80.1% do not produce wildly different scores.

Status bands:
    0-39   Critical
    40-59  Poor
    60-74  Fair
    75-89  Good
    90-100 Excellent
"""
from config import Config
from models.schemas import HealthFactor, HealthResult, status_for_score


def _gradual_impact(value, threshold, max_penalty, scale, label):
    """Return (impact, reason) with a gradual penalty above ``threshold``."""
    value = value or 0.0
    if value < threshold:
        return 0, f"{label} usage is healthy at {value:.1f}%"
    penalty = min(max_penalty, round((value - threshold) * scale))
    return -penalty, (
        f"{label} usage is at {value:.1f}% (above the {threshold:.0f}% "
        f"threshold - reduced by {penalty} points)"
    )


def _gradual_count_impact(count, threshold, max_penalty, scale, label):
    if count <= threshold:
        return 0, f"{label} count is normal ({count})"
    penalty = min(max_penalty, round((count - threshold) * scale))
    return -penalty, (
        f"High {label.lower()} count ({count}) - reduced by {penalty} points"
    )


def compute_health_score(cpu, ram, disk, process_count=None):
    """Compute the health score with transparent factors.

    ``network`` is intentionally not part of the score: this application does
    not yet compute a meaningful network-health metric, so it must not appear
    as a fake/placeholder factor.
    """
    factors = []
    issues = []

    impact, reason = _gradual_impact(
        cpu, Config.HEALTH_CPU_LOW, Config.HEALTH_CPU_MAX_PENALTY,
        Config.HEALTH_CPU_SCALE, "CPU")
    factors.append(HealthFactor("CPU", impact, reason))

    impact, reason = _gradual_impact(
        ram, Config.HEALTH_RAM_LOW, Config.HEALTH_RAM_MAX_PENALTY,
        Config.HEALTH_RAM_SCALE, "RAM")
    factors.append(HealthFactor("RAM", impact, reason))

    impact, reason = _gradual_impact(
        disk, Config.HEALTH_DISK_LOW, Config.HEALTH_DISK_MAX_PENALTY,
        Config.HEALTH_DISK_SCALE, "Disk")
    factors.append(HealthFactor("Disk", impact, reason))

    if process_count is not None:
        impact, reason = _gradual_count_impact(
            process_count, Config.HEALTH_PROCESS_THRESHOLD,
            Config.HEALTH_PROCESS_MAX_PENALTY, Config.HEALTH_PROCESS_SCALE,
            "Process")
        factors.append(HealthFactor("Processes", impact, reason))
    else:
        factors.append(HealthFactor("Processes", 0, "Process count is not available"))

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
            issues.append(f"{f.factor}: {f.reason}")

    return HealthResult(
        score=score,
        status=status["label"],
        color=status["color"],
        factors=factors,
        issues=issues,
    )

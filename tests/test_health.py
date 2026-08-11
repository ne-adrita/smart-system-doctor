"""Tests for the System Health Score calculation."""
from services.health_analyzer import compute_health_score


def _score(cpu, ram, disk, process_count=None):
    return compute_health_score(cpu, ram, disk, process_count).score


def test_cpu_low_is_healthy():
    result = compute_health_score(5, 20, 30)
    assert result.score >= 90
    assert result.status == "Excellent"
    assert all(f.impact >= 0 for f in result.factors)


def test_cpu_high_decreases_score():
    low = _score(10, 30, 30)
    high = _score(95, 30, 30)
    assert high < low
    cpu_factor = next(f for f in compute_health_score(95, 30, 30).factors
                      if f.factor == "CPU")
    assert cpu_factor.impact < 0


def test_ram_high_decreases_score():
    low = _score(10, 20, 30)
    high = _score(10, 95, 30)
    assert high < low
    ram_factor = next(f for f in compute_health_score(10, 95, 30).factors
                      if f.factor == "RAM")
    assert ram_factor.impact < 0


def test_disk_high_decreases_score():
    low = _score(10, 20, 30)
    high = _score(10, 20, 98)
    assert high < low


def test_score_never_negative():
    assert _score(100, 100, 100) >= 0


def test_issues_explain_critical():
    result = compute_health_score(100, 100, 100)
    assert result.score < 40
    assert result.status == "Critical"
    assert len(result.issues) > 0

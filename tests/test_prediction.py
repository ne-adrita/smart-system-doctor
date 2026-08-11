"""Tests for trend-based predictive analysis."""
from services.prediction_service import (
    RELIABILITY_THRESHOLD,
    linear_regression,
    get_predictions,
)


def test_linear_regression_increasing():
    a, b, r2 = linear_regression([10, 20, 30, 40, 50])
    assert b > 0
    assert r2 > 0.99  # perfectly linear series


def test_linear_regression_decreasing():
    a, b, _ = linear_regression([50, 40, 30, 20, 10])
    assert b < 0


def test_linear_regression_flat():
    a, b, _ = linear_regression([30, 30, 30, 30, 30])
    assert abs(b) < 0.001


def test_increasing_series_forecasts_increasing():
    series = list(range(30, 80, 5))  # steadily increasing
    a, b, _ = linear_regression(series)
    assert b > 0.5  # classified as "increasing"


def test_stable_series_forecasts_stable():
    series = [50, 51, 49, 50, 50, 51, 50, 50, 49, 50]
    a, b, _ = linear_regression(series)
    assert -0.5 <= b <= 0.5


def test_noisy_series_has_low_reliability():
    # Random-looking data fits a line poorly, so R-squared must be low.
    a, b, r2 = linear_regression([10, 80, 15, 90, 12, 85, 14, 88, 11])
    assert r2 < RELIABILITY_THRESHOLD


def test_clean_series_has_high_reliability():
    a, b, r2 = linear_regression([20, 30, 40, 50, 60, 70])
    assert r2 > 0.95


def test_predictions_unavailable_without_history():
    result = get_predictions()
    assert result["available"] is False
    assert "reason" in result

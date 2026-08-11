"""Trend-Based Predictive Analysis.

This is honest trend-based forecasting built on historical records stored in
SQLite. A least-squares linear regression is fit over the recent history for
each resource, then extrapolated a short horizon.

Reliability: the coefficient of determination (R²) is reported so users can
see how well the historical data actually fits a linear trend. A low R² means
the recent data is highly variable and the forecast should not be treated as
trustworthy.

Important: this is NOT a machine-learning model. Forecasts are statistical
extrapolations of observed trends and should never be interpreted as
guarantees of future behaviour.
"""
import statistics

from config import Config
from database import get_history
from utils.logging_utils import get_logger

logger = get_logger(__name__)

RELIABILITY_THRESHOLD = 0.3  # below this, the trend is not reliable


def linear_regression(points):
    """Fit y = a + b*x via least squares.

    Returns ``(a, b, r_squared)`` where ``r_squared`` is the coefficient of
    determination for the fit.
    """
    n = len(points)
    if n < 2:
        r2 = 1.0 if n == 1 else 0.0
        return (points[0] if points else 0.0), 0.0, r2
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(points) / n
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom == 0:
        return mean_y, 0.0, 0.0
    b = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, points)) / denom
    a = mean_y - b * mean_x

    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, points))
    ss_tot = sum((y - mean_y) ** 2 for y in points)
    r_squared = 1.0 if ss_tot == 0 else 1.0 - ss_res / ss_tot
    return a, b, r_squared


def _trend_label(slope):
    if slope > 0.5:
        return "increasing"
    if slope < -0.5:
        return "decreasing"
    return "stable"


def _risk_level(current, trend, forecast_peak):
    if trend == "increasing" and forecast_peak > 80:
        return "High"
    if trend == "increasing" and forecast_peak > 60:
        return "Moderate"
    if current > 80:
        return "Moderate"
    return "Low"


def _forecast_series(points, name):
    """Produce a forecast dict for one resource series."""
    current = round(points[-1], 2)
    a, b, r_squared = linear_regression(points)

    # Residual standard deviation => plausible forecast band.
    residuals = [y - (a + b * i) for i, y in enumerate(points)]
    try:
        spread = statistics.pstdev(residuals)
    except Exception:
        spread = 0.0

    horizon = Config.PREDICTION_HORIZON_POINTS
    n = len(points)
    peak_i = n - 1 + horizon
    forecast_peak = min(100.0, max(0.0, a + b * peak_i))

    trend = _trend_label(b)
    next_val = min(100.0, max(0.0, a + b * n))
    low = max(0.0, round(next_val - 2 * spread, 1))
    high = min(100.0, round(next_val + 2 * spread, 1))

    reliability = max(0.0, min(1.0, r_squared))
    if reliability < RELIABILITY_THRESHOLD:
        reliability_note = (
            "Forecast reliability is low because recent system usage is highly variable."
        )
    else:
        reliability_note = None

    return {
        "current": current,
        "trend": trend,
        "slope_per_interval": round(b, 3),
        "forecast": round(next_val, 1),
        "range_low": low,
        "range_high": high,
        "reliability": round(reliability, 3),
        "reliability_note": reliability_note,
        "risk": _risk_level(current, trend, forecast_peak),
        "model": "linear regression (least squares) over recent history",
        "sample_count": n,
    }


def get_predictions(hours=2):
    """Compute trend-based forecasts for CPU, RAM and disk."""
    history = get_history(hours=hours, limit=Config.MAX_HISTORY_POINTS)
    if len(history) < Config.PREDICTION_MIN_SAMPLES:
        return {
            "available": False,
            "reason": f"Need at least {Config.PREDICTION_MIN_SAMPLES} historical "
                      "samples to build a forecast.",
            "cpu": None,
            "ram": None,
            "disk": None,
        }

    series = {
        "cpu": [r["cpu"] for r in history if r.get("cpu") is not None],
        "ram": [r["ram"] for r in history if r.get("ram") is not None],
        "disk": [r["disk"] for r in history if r.get("disk") is not None],
    }
    result = {"available": True, "based_on": f"last {len(history)} recorded samples"}
    for resource, points in series.items():
        if len(points) >= Config.PREDICTION_MIN_SAMPLES:
            result[resource] = _forecast_series(points, resource)
        else:
            result[resource] = None
    return result

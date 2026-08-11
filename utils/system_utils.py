"""Small helpers shared across the application."""
import time
from datetime import datetime


def format_bytes(value, suffix="B"):
    """Human-readable byte size."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "0 B"
    for unit in ("", "K", "M", "G", "T", "P"):
        if abs(value) < 1024.0:
            return f"{value:.1f} {unit}{suffix}"
        value /= 1024.0
    return f"{value:.1f} E{suffix}"


def format_uptime(seconds):
    """Human-readable uptime from seconds."""
    seconds = max(int(seconds), 0)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h {minutes}m"
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def ts_iso(seconds=None):
    return datetime.fromtimestamp(seconds if seconds is not None else time.time()).isoformat()


def clamp(value, low=0, high=100):
    return max(low, min(high, value))

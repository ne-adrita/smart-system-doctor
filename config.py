"""Environment-based configuration for Smart System Doctor Pro.

Values can be overridden through a local ``.env`` file or OS environment
variables. No sensitive values are hard-coded in the source tree.
"""
import os
import platform
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    """Load a simple ``KEY=VALUE`` .env file without external dependencies."""
    if not path.exists():
        return
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


_load_dotenv(BASE_DIR / ".env")


def _env(key: str, default):
    return os.environ.get(key, default)


def _env_bool(key: str, default: bool) -> bool:
    raw = _env(key, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _env_int(key: str, default: int) -> int:
    try:
        return int(_env(key, default))
    except (TypeError, ValueError):
        return default


def _env_float(key: str, default: float) -> float:
    try:
        return float(_env(key, default))
    except (TypeError, ValueError):
        return default


class Config:
    # --- Flask / server -------------------------------------------------
    FLASK_HOST = _env("FLASK_HOST", "127.0.0.1")
    FLASK_PORT = _env_int("FLASK_PORT", 5001)
    FLASK_DEBUG = _env_bool("FLASK_DEBUG", False)
    SECRET_KEY = _env("FLASK_SECRET_KEY", "smart-system-doctor-local")

    # --- Paths ----------------------------------------------------------
    DATABASE_PATH = _env("DATABASE_PATH", str(BASE_DIR / "system_logs.db"))
    LOG_DIR = _env("LOG_DIR", str(BASE_DIR / "logs"))
    LOG_FILE = _env("LOG_FILE", "app.log")
    REPORT_DIR = _env("REPORT_DIR", str(BASE_DIR / "reports"))

    # --- Monitoring intervals (seconds) ---------------------------------
    # Fast metrics (CPU / RAM) are computed on demand by the API.
    DISK_NETWORK_INTERVAL = _env_int("DISK_NETWORK_INTERVAL", 5)
    HISTORY_INTERVAL = _env_int("HISTORY_INTERVAL", 10)
    SECURITY_SCAN_INTERVAL = _env_int("SECURITY_SCAN_INTERVAL", 15)
    PORT_SCAN_INTERVAL = _env_int("PORT_SCAN_INTERVAL", 30)
    PRUNE_INTERVAL = _env_int("PRUNE_INTERVAL", 3600)

    # --- Database -------------------------------------------------------
    HISTORY_RETENTION_DAYS = _env_int("HISTORY_RETENTION_DAYS", 14)
    MAX_HISTORY_POINTS = _env_int("MAX_HISTORY_POINTS", 200)
    DOWNLOAD_POINTS = _env_int("DOWNLOAD_POINTS", 120)

    # --- Security analysis ----------------------------------------------
    # Suspicion score weights (documented in README).
    WEIGHT_SUSPICIOUS_FILENAME = _env_int("WEIGHT_SUSPICIOUS_FILENAME", 15)
    WEIGHT_SUSPICIOUS_PATH = _env_int("WEIGHT_SUSPICIOUS_PATH", 20)
    WEIGHT_NETWORK_ACTIVITY = _env_int("WEIGHT_NETWORK_ACTIVITY", 20)
    WEIGHT_HIGH_CPU = _env_int("WEIGHT_HIGH_CPU", 10)
    WEIGHT_HIGH_MEMORY = _env_int("WEIGHT_HIGH_MEMORY", 10)
    WEIGHT_UNUSUAL_PARENT = _env_int("WEIGHT_UNUSUAL_PARENT", 15)
    WEIGHT_PRIVILEGED_ANOMALY = _env_int("WEIGHT_PRIVILEGED_ANOMALY", 10)

    # Thresholds for the suspicion classifier.
    SUSPICIOUS_CPU_PERCENT = _env_float("SUSPICIOUS_CPU_PERCENT", 70.0)
    SUSPICIOUS_MEMORY_PERCENT = _env_float("SUSPICIOUS_MEMORY_PERCENT", 50.0)
    NETWORK_FLAG_CUTOFF = _env_int("NETWORK_FLAG_CUTOFF", 15)

    # Upper bound for heuristic strength of findings (never claim certainty).
    HEURISTIC_STRENGTH_CEILING = _env_float("HEURISTIC_STRENGTH_CEILING", 0.9)

    # --- Health scoring --------------------------------------------------
    # Gradual penalty model: penalty grows from the LOW threshold up to
    # MAX_PENALTY at a rate of SCALE points per usage percentage point.
    HEALTH_CPU_LOW = _env_float("HEALTH_CPU_LOW", 60.0)
    HEALTH_CPU_MAX_PENALTY = _env_int("HEALTH_CPU_MAX_PENALTY", 40)
    HEALTH_CPU_SCALE = _env_float("HEALTH_CPU_SCALE", 1.0)
    HEALTH_RAM_LOW = _env_float("HEALTH_RAM_LOW", 60.0)
    HEALTH_RAM_MAX_PENALTY = _env_int("HEALTH_RAM_MAX_PENALTY", 40)
    HEALTH_RAM_SCALE = _env_float("HEALTH_RAM_SCALE", 1.0)
    HEALTH_DISK_LOW = _env_float("HEALTH_DISK_LOW", 70.0)
    HEALTH_DISK_MAX_PENALTY = _env_int("HEALTH_DISK_MAX_PENALTY", 30)
    HEALTH_DISK_SCALE = _env_float("HEALTH_DISK_SCALE", 1.0)
    HEALTH_PROCESS_THRESHOLD = _env_int("HEALTH_PROCESS_THRESHOLD", 500)
    HEALTH_PROCESS_MAX_PENALTY = _env_int("HEALTH_PROCESS_MAX_PENALTY", 10)
    HEALTH_PROCESS_SCALE = _env_float("HEALTH_PROCESS_SCALE", 0.1)

    # --- Predictions -----------------------------------------------------
    PREDICTION_HORIZON_POINTS = _env_int("PREDICTION_HORIZON_POINTS", 5)
    PREDICTION_MIN_SAMPLES = _env_int("PREDICTION_MIN_SAMPLES", 8)

    # --- Process protection ---------------------------------------------
    # Critical system processes that may never be terminated casually.
    PROTECTED_PROCESS_NAMES = set(
        name.strip().lower()
        for name in _env(
            "PROTECTED_PROCESS_NAMES",
            "system,systemd,init,kernel_task,launchd,svchost,wininit,smss,"
            "csrss,services,lsass,winlogon,wininit,securityd,taskgated,"
            "syslogd,mds,mdworker,loginwindow,WindowServer,opencoded,"
            "coreaudiod,coreduetd,cfprefsd,distnoted",
        ).split(",")
        if name.strip()
    )
    PROTECTED_PROCESS_PIDS = set(
        int(pid) for pid in _env("PROTECTED_PROCESS_PIDS", "1,0").split(",") if pid.strip()
    )
    # Allow force-killing protected processes only when explicitly enabled.
    ALLOW_FORCE_PROTECTED = _env_bool("ALLOW_FORCE_PROTECTED", False)
    TERMINATE_TIMEOUT = _env_int("TERMINATE_TIMEOUT", 3)

    # --- Known services --------------------------------------------------
    # Well-known port -> service mapping used to label listening ports.
    KNOWN_PORTS = {
        21: "FTP",
        22: "SSH",
        23: "Telnet",
        25: "SMTP",
        53: "DNS",
        80: "HTTP",
        110: "POP3",
        143: "IMAP",
        443: "HTTPS",
        445: "SMB",
        993: "IMAPS",
        995: "POP3S",
        3306: "MySQL",
        3389: "RDP",
        5432: "PostgreSQL",
        6379: "Redis",
        8080: "HTTP-Alt",
        27017: "MongoDB",
    }

    # --- Misc ------------------------------------------------------------
    OS_NAME = platform.system()
    DB_TIMEOUT = 10


class TestingConfig(Config):
    FLASK_DEBUG = False
    # Use a fresh temporary file per test process. ":memory:" looks nice but
    # each thread-local connection would open its own empty in-memory database.
    DATABASE_PATH = tempfile.NamedTemporaryFile(
        suffix=".db", prefix="ssd-test-", delete=False
    ).name
    HISTORY_INTERVAL = 60
    SECURITY_SCAN_INTERVAL = 60
    PORT_SCAN_INTERVAL = 60
    PREDICTION_MIN_SAMPLES = 4
    DISABLE_BACKGROUND = True


def get_config() -> Config:
    if _env_bool("SSD_TESTING", False):
        return TestingConfig()
    return Config()

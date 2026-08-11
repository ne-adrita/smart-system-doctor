"""Process helpers: validation, protection checks and safe termination."""
import psutil

from config import Config
from utils.logging_utils import get_logger

logger = get_logger(__name__)


def validate_pid(pid):
    """Return a positive integer PID or raise ValueError."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        raise ValueError("Invalid PID: must be an integer")
    if pid <= 0:
        raise ValueError("Invalid PID: must be a positive integer")
    return pid


def is_protected(pid, name=None, exe=None, username=None):
    """Determine whether a process is on the protected-process list."""
    if pid in Config.PROTECTED_PROCESS_PIDS:
        return True
    if name:
        lowered = name.strip().lower()
        for protected in Config.PROTECTED_PROCESS_NAMES:
            if protected in lowered or lowered in protected:
                return True
    return False


def get_process_details(pid):
    """Return a safe, validated process summary or raise psutil exceptions."""
    p = psutil.Process(pid)
    try:
        name = p.name()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        name = None
    try:
        exe = p.exe()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        exe = None
    try:
        username = p.username()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        username = None

    if is_protected(pid, name, exe, username):
        raise PermissionError(f"PID {pid} ({name or 'unknown'}) is a protected system process")
    return {"pid": pid, "name": name, "exe": exe, "username": username}


def _terminate(pid, force=False):
    """Perform the actual termination. Raises psutil exceptions."""
    p = psutil.Process(pid)
    if force:
        p.kill()
    else:
        p.terminate()

    gone, alive = psutil.wait_procs([p], timeout=Config.TERMINATE_TIMEOUT)
    if alive:
        return {"terminated": False, "reason": "Process still running after terminate signal"}
    return {"terminated": True}


def terminate_process(pid, force=False):
    """Safely terminate a process.

    Returns a structured dict. Raises ValueError / PermissionError /
    psutil.NoSuchProcess for caller-friendly error mapping.
    """
    pid = validate_pid(pid)
    details = get_process_details(pid)  # raises if protected
    result = _terminate(pid, force=force)
    result["details"] = details
    return result

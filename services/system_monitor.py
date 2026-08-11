"""Centralized system monitoring using psutil.

All psutil system calls live here so the rest of the application does not
re-implement them. Every call handles psutil exceptions specifically.
"""
import os
import platform
import time
from datetime import datetime

import psutil

from utils.logging_utils import get_logger
from utils.system_utils import format_bytes, format_uptime

logger = get_logger(__name__)


def get_cpu():
    """CPU usage in percent (since the last call)."""
    try:
        return round(psutil.cpu_percent(interval=None), 2)
    except Exception:
        logger.warning("cpu_percent failed", exc_info=True)
        return 0.0


def get_cpu_info():
    info = {"count": psutil.cpu_count(logical=True) or 1,
            "physical_count": psutil.cpu_count(logical=False) or 1}
    try:
        freq = psutil.cpu_freq()
        if freq:
            info["frequency_mhz"] = round(freq.current, 2)
            info["min_mhz"] = round(freq.min, 2)
            info["max_mhz"] = round(freq.max, 2)
    except Exception:
        logger.debug("cpu_freq unavailable", exc_info=True)
    return info


def get_memory():
    vm = psutil.virtual_memory()
    return {
        "total": vm.total,
        "available": vm.available,
        "used": vm.used,
        "percent": round(vm.percent, 2),
        "total_human": format_bytes(vm.total),
        "used_human": format_bytes(vm.used),
        "available_human": format_bytes(vm.available),
    }


def get_swap():
    try:
        swap = psutil.swap_memory()
        return {
            "total": swap.total,
            "used": swap.used,
            "percent": round(swap.percent, 2),
            "total_human": format_bytes(swap.total),
            "used_human": format_bytes(swap.used),
        }
    except Exception:
        logger.debug("swap unavailable", exc_info=True)
        return {}


def get_disk(path="/"):
    try:
        usage = psutil.disk_usage(path)
        return {
            "path": path,
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "percent": round(usage.percent, 2),
            "total_human": format_bytes(usage.total),
            "used_human": format_bytes(usage.used),
            "free_human": format_bytes(usage.free),
        }
    except (psutil.Error, OSError):
        logger.warning("disk_usage failed for %s", path, exc_info=True)
        return {"path": path, "percent": 0.0}


def get_disk_io():
    try:
        io = psutil.disk_io_counters()
        if not io:
            return {}
        return {
            "read_bytes": io.read_bytes,
            "write_bytes": io.write_bytes,
            "read_count": io.read_count,
            "write_count": io.write_count,
            "read_human": format_bytes(io.read_bytes),
            "write_human": format_bytes(io.write_bytes),
        }
    except Exception:
        logger.debug("disk_io_counters unavailable", exc_info=True)
        return {}


def get_network():
    try:
        net = psutil.net_io_counters()
        return {
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv,
            "packets_sent": net.packets_sent,
            "packets_recv": net.packets_recv,
            "bytes_sent_human": format_bytes(net.bytes_sent),
            "bytes_recv_human": format_bytes(net.bytes_recv),
        }
    except Exception:
        logger.debug("net_io_counters unavailable", exc_info=True)
        return {}


def get_uptime():
    try:
        boot = psutil.boot_time()
        uptime = int(time.time() - boot)
        return {
            "uptime_seconds": uptime,
            "uptime_human": format_uptime(uptime),
            "boot_time_iso": datetime.fromtimestamp(boot).isoformat(),
        }
    except Exception:
        logger.debug("boot_time unavailable", exc_info=True)
        return {"uptime_seconds": 0, "uptime_human": "unknown", "boot_time_iso": None}


def get_os_info():
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "hostname": platform.node(),
        "python_version": platform.python_version(),
        "os_name": psutil.os.name,
    }


def get_process_count():
    try:
        return len(psutil.pids())
    except Exception:
        logger.warning("pids() failed", exc_info=True)
        return 0


def get_system_metrics():
    """Structured snapshot of fast + moderate system metrics."""
    return {
        "cpu": get_cpu(),
        "memory": get_memory(),
        "disk": get_disk(),
        "network": get_network(),
        "process_count": get_process_count(),
        "uptime": get_uptime(),
        "os": get_os_info(),
    }

"""Process monitoring.

Cheap attributes are collected for the full list; expensive attributes
(executable, username, cmdline, connections, open files) are gathered only on
demand via :func:`get_process_details`.

CPU percentage is computed from per-process CPU-time deltas so the first call
does not return a misleading ``0.0``.
"""
import time
from collections import defaultdict

import psutil

from utils.logging_utils import get_logger

logger = get_logger(__name__)

CHEAP_ATTRS = ("pid", "name", "ppid", "status", "create_time", "num_threads",
               "memory_info", "memory_percent")

SORT_KEYS = {"cpu", "ram", "pid", "name"}


class ProcessMonitor:
    def __init__(self):
        self._cpu_times = {}
        self._last_poll = time.monotonic()

    def _warm_cpu_cache(self, procs):
        """Record baseline CPU times so the next call reports a real value."""
        now = time.monotonic()
        elapsed = now - self._last_poll
        self._last_poll = now
        if elapsed <= 0:
            return

        new_times = {}
        for p in procs:
            pid = p.info.get("pid")
            try:
                user, system = p.cpu_times()[:2]
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            prev = self._cpu_times.get(pid)
            if prev is not None:
                delta_cpu = max((user - prev[0]) + (system - prev[1]), 0)
                new_times[pid] = (user, system, (delta_cpu / elapsed) * 100.0)
            else:
                new_times[pid] = (user, system, 0.0)
        self._cpu_times = new_times

    def _cpu_percent(self, pid):
        entry = self._cpu_times.get(pid)
        if not entry:
            return 0.0
        _, _, pct = entry
        cores = max(psutil.cpu_count(logical=True) or 1, 1)
        return round(pct / cores, 2)

    def get_processes(self, sort_by="cpu", order="desc", limit=50, filter_="all"):
        """Return a cheap process list (no exe/username/connections)."""
        if sort_by not in SORT_KEYS:
            sort_by = "cpu"
        reverse = order.lower() == "desc"

        procs = list(
            psutil.process_iter(
                ["pid", "name", "ppid", "status", "create_time", "num_threads",
                 "memory_percent"]
            )
        )
        self._warm_cpu_cache(procs)

        rows = []
        for p in procs:
            pid = p.info["pid"]
            mem_percent = p.info.get("memory_percent") or 0.0
            try:
                memory_rss = p.info.get("memory_info", None)
                rss = memory_rss.rss if memory_rss else 0
            except Exception:
                rss = 0
            rows.append({
                "pid": pid,
                "name": p.info.get("name"),
                "ppid": p.info.get("ppid"),
                "cpu_percent": self._cpu_percent(pid),
                "memory_percent": round(mem_percent, 2),
                "memory_rss": rss,
                "memory_rss_human": _human_rss(rss),
                "status": p.info.get("status"),
                "num_threads": p.info.get("num_threads"),
                "create_time": p.info.get("create_time"),
            })

        if filter_ == "suspicious":
            rows = [r for r in rows if r["cpu_percent"] > 50 or r["memory_percent"] > 50]
        elif filter_ == "cpu-heavy":
            rows = [r for r in rows if r["cpu_percent"] > 30]

        rows.sort(key=lambda r: (r.get(sort_by) if r.get(sort_by) is not None else 0),
                  reverse=reverse)
        return rows[:limit] if limit else rows

    def get_process_details(self, pid):
        """Return full on-demand details for a single process."""
        p = psutil.Process(pid)
        details = {
            "pid": p.pid,
            "name": _safe(lambda: p.name()),
            "ppid": _safe(lambda: p.ppid()),
            "ppid_name": None,
            "status": _safe(lambda: p.status()),
            "username": _safe(lambda: p.username()),
            "exe": _safe(lambda: p.exe()),
            "cmdline": _safe(lambda: p.cmdline()),
            "cwd": _safe(lambda: p.cwd()),
            "num_threads": _safe(lambda: p.num_threads()),
            "create_time": _safe(lambda: time.ctime(p.create_time())),
            "cpu_percent": self._cpu_percent(pid),
            "memory_percent": _safe(lambda: round(p.memory_percent(), 2)),
            "memory": _safe(lambda: _mem_dict(p.memory_info())),
            "connections": _safe(lambda: _conns(p.connections())),
            "open_files": _safe(lambda: _files(p.open_files())),
        }
        ppid = details.get("ppid")
        if isinstance(ppid, int) and ppid > 0:
            try:
                details["ppid_name"] = psutil.Process(ppid).name()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                details["ppid_name"] = None
        return details


def _human_rss(rss):
    try:
        from utils.system_utils import format_bytes
        return format_bytes(rss)
    except Exception:
        return str(rss)


def _mem_dict(mem):
    if not mem:
        return {}
    keys = ("rss", "vms", "shared", "data")
    return {k: getattr(mem, k, None) for k in keys}


def _conns(conns):
    if not conns:
        return []
    result = []
    for c in conns:
        try:
            result.append({
                "family": str(c.family),
                "type": str(c.type),
                "laddr": c.laddr._asdict() if c.laddr else None,
                "raddr": c.raddr._asdict() if c.raddr else None,
                "status": c.status,
            })
        except Exception:
            continue
    return result


def _files(files):
    if not files:
        return []
    return [f.path for f in files]


def _safe(func, default=None):
    try:
        return func()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return default
    except Exception:
        return default


_process_monitor = ProcessMonitor()


def get_processes(sort_by="cpu", order="desc", limit=50, filter_="all"):
    return _process_monitor.get_processes(sort_by, order, limit, filter_)


def get_process_details(pid):
    return _process_monitor.get_process_details(pid)

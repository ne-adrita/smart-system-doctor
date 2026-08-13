"""Process Monitor unit tests: fields, sorting, memory, CPU, details."""
import os
import subprocess
import sys
import time

import psutil
import pytest

from services.process_monitor import ProcessMonitor, SORT_FIELD_MAP


@pytest.fixture()
def monitor():
    return ProcessMonitor()


def _spawn_sleep(seconds=60):
    return subprocess.Popen(
        [sys.executable, "-c", f"import time; time.sleep({seconds})"]
    )


def test_sort_field_map_keys():
    assert set(SORT_FIELD_MAP) == {"cpu", "ram", "pid", "name"}
    assert SORT_FIELD_MAP["cpu"] == "cpu_percent"
    assert SORT_FIELD_MAP["ram"] == "memory_percent"


def test_process_list_returns_rows_with_required_fields(monitor):
    rows = monitor.get_processes(limit=20)
    assert isinstance(rows, list)
    assert len(rows) > 0
    required = {
        "pid", "name", "ppid", "cpu_percent", "memory_percent",
        "memory_rss", "memory_rss_human", "status", "username",
        "num_threads", "create_time",
    }
    for row in rows[:5]:
        assert required.issubset(row.keys())


def test_process_list_cpu_sort_desc(monitor):
    rows = monitor.get_processes(sort_by="cpu", limit=50)
    cpus = [r["cpu_percent"] for r in rows]
    assert cpus == sorted(cpus, reverse=True)


def test_process_list_cpu_sort_asc(monitor):
    rows = monitor.get_processes(sort_by="cpu", order="asc", limit=50)
    cpus = [r["cpu_percent"] for r in rows]
    assert cpus == sorted(cpus)


def test_process_list_ram_sort_desc(monitor):
    rows = monitor.get_processes(sort_by="ram", limit=50)
    mems = [r["memory_percent"] for r in rows]
    assert mems == sorted(mems, reverse=True)


def test_process_list_pid_sort_asc(monitor):
    rows = monitor.get_processes(sort_by="pid", order="asc", limit=50)
    pids = [r["pid"] for r in rows]
    assert pids == sorted(pids)


def test_process_list_name_sort_asc(monitor):
    rows = monitor.get_processes(sort_by="name", order="asc", limit=50)
    names = [r["name"] for r in rows]
    assert names == sorted(names, key=str.lower)


def test_invalid_sort_falls_back_to_cpu(monitor):
    rows = monitor.get_processes(sort_by="bogus", limit=10)
    assert len(rows) > 0
    cpus = [r["cpu_percent"] for r in rows]
    assert cpus == sorted(cpus, reverse=True)


def test_memory_rss_real_and_non_negative(monitor):
    rows = monitor.get_processes(limit=100)
    for row in rows:
        assert row["memory_rss"] >= 0
        assert isinstance(row["memory_rss_human"], str)
    # Our own test process should have non-zero RSS.
    self_row = next((r for r in rows if r["pid"] == os.getpid()), None)
    if self_row:
        assert self_row["memory_rss"] > 0


def test_cpu_baseline_then_delta(monitor):
    proc = _spawn_sleep()
    try:
        # First refresh establishes the baseline (may be 0.0).
        monitor.get_processes(limit=0)
        time.sleep(1.0)
        rows = monitor.get_processes(limit=0)
        row = next((r for r in rows if r["pid"] == proc.pid), None)
        # A sleeping process is allowed to report 0.0 or a small value;
        # the key point is the delta path returns a real number, not None.
        assert row is not None
        assert row["cpu_percent"] == pytest.approx(
            max(0.0, row["cpu_percent"]), abs=0.01
        )
        assert row["pid"] == proc.pid
    finally:
        if proc.poll() is None:
            proc.kill()


def test_busy_process_reports_real_cpu_percent(monitor):
    """A process burning one core must report a meaningful CPU percentage.

    Regression: the CPU value used to be divided by the logical core count,
    so a fully-busy single-thread process would show ~12%% on an 8-core host
    instead of ~100%%.
    """
    busy = subprocess.Popen(
        [sys.executable, "-c", "while True: pass"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        monitor.get_processes(limit=0)  # establish the baseline
        time.sleep(2.0)
        rows = monitor.get_processes(limit=0)
        row = next((r for r in rows if r["pid"] == busy.pid), None)
        assert row is not None
        assert row["cpu_percent"] > 50, (
            f"burnt one core but cpu_percent={row['cpu_percent']}; "
            "the /cores division bug is back"
        )
    finally:
        if busy.poll() is None:
            busy.kill()
            busy.wait()


def test_process_appears_and_disappears(monitor):
    proc = _spawn_sleep()
    try:
        rows = monitor.get_processes(limit=0)
        assert any(r["pid"] == proc.pid for r in rows)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        else:
            proc.wait()
    # Give psutil a moment to observe the exit, then verify it is gone.
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        rows = monitor.get_processes(limit=0)
        if not any(r["pid"] == proc.pid for r in rows):
            break
        time.sleep(0.3)
    rows = monitor.get_processes(limit=0)
    assert not any(r["pid"] == proc.pid for r in rows)


def test_details_include_all_fields(monitor):
    proc = _spawn_sleep()
    try:
        details = monitor.get_process_details(proc.pid)
        for key in ("pid", "name", "ppid", "ppid_name", "status", "username",
                    "exe", "cmdline", "cwd", "num_threads", "create_time",
                    "cpu_percent", "memory_percent", "memory", "connections",
                    "open_files"):
            assert key in details
        assert details["pid"] == proc.pid
    finally:
        if proc.poll() is None:
            proc.kill()


def test_details_nonexistent_pid_raises(monitor):
    with pytest.raises(psutil.NoSuchProcess):
        monitor.get_process_details(99999999)


def test_details_access_denied_raises(monkeypatch):
    """A process whose identity cannot be read must surface AccessDenied so
    the API can return a clear error instead of silently blank fields."""
    real_process = psutil.Process()

    class DeniedProcess:
        pid = real_process.pid

        def name(self):
            raise psutil.AccessDenied(self.pid, "test")

    monkeypatch.setattr("psutil.Process", lambda pid: DeniedProcess())
    with pytest.raises(psutil.AccessDenied):
        ProcessMonitor().get_process_details(real_process.pid)


def test_filter_suspicious_returns_subset(monitor):
    all_rows = monitor.get_processes(limit=0)
    suspicious = monitor.get_processes(limit=0, filter_="suspicious")
    assert all(
        r["cpu_percent"] > 50 or r["memory_percent"] > 50 for r in suspicious
    )
    assert len(suspicious) <= len(all_rows)


def test_inaccessible_process_does_not_crash_list(monitor, monkeypatch):
    """A process that denies access to its memory info must not break the
    whole process list. Column values fall back to safe defaults."""
    real = psutil.Process()

    class SquashyProcess:
        """Wraps a real process but raises AccessDenied for memory fields."""

        def __init__(self, inner):
            self._inner = inner
            p = inner.as_dict(ad_value=None)
            self.info = {
                "pid": p.get("pid"),
                "name": p.get("name"),
                "ppid": p.get("ppid"),
                "status": p.get("status"),
                "create_time": p.get("create_time"),
                "memory_percent": p.get("memory_percent"),
                "username": p.get("username"),
            }

        def cpu_times(self):
            return self._inner.cpu_times()

        def memory_info(self):
            raise psutil.AccessDenied(self._inner.pid, "test")

        def memory_percent(self):
            raise psutil.AccessDenied(self._inner.pid, "test")

        def num_threads(self):
            return self._inner.num_threads()

    wrapped = SquashyProcess(real)
    monkeypatch.setattr(
        "services.process_monitor.psutil.process_iter",
        lambda attrs=None: [wrapped],
    )
    rows = monitor.get_processes(limit=10)
    assert len(rows) == 1
    assert rows[0]["memory_rss"] == 0
    assert rows[0]["memory_percent"] == 0.0
    assert "pid" in rows[0]

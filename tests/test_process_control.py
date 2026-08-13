"""Process control tests: PID validation, protection, graceful vs force kill."""
import subprocess
import sys

import psutil
import pytest

from utils.process_utils import _terminate, terminate_process, validate_pid


def test_validate_pid_accepts_positive_int():
    assert validate_pid(42) == 42
    assert validate_pid("42") == 42


@pytest.mark.parametrize("bad", [-1, 0, "abc", None, 1.5, "12x"])
def test_validate_pid_rejects_invalid(bad):
    with pytest.raises(ValueError):
        validate_pid(bad)


def test_protected_pid_is_rejected():
    with pytest.raises(PermissionError):
        terminate_process(1)  # PID 1 is always protected


def test_nonexistent_pid_raises():
    with pytest.raises(psutil.NoSuchProcess):
        terminate_process(99999999)


def test_terminate_flags_force_true():
    # Spawn a short-lived child so we can exercise _terminate logic paths.
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        result = terminate_process(proc.pid, force=False)
        assert result["terminated"] is True
        assert "details" in result
        assert result["details"]["pid"] == proc.pid
    finally:
        if proc.poll() is None:
            proc.kill()


def test_zombie_process_counts_as_terminated(monkeypatch):
    """A zombie has already exited; it must not be reported as still running
    just because its parent has not reaped it yet."""
    class FakeProc:
        pid = 4242

        def status(self):
            return psutil.STATUS_ZOMBIE

        def terminate(self):
            pass

        def kill(self):
            pass

    fake = FakeProc()
    monkeypatch.setattr(psutil, "Process", lambda pid: fake)
    monkeypatch.setattr(psutil, "wait_procs", lambda procs, timeout: ([], [fake]))
    result = _terminate(4242, force=False)
    assert result["terminated"] is True


def test_true_running_process_counts_as_not_terminated(monkeypatch):
    class FakeProc:
        pid = 4243

        def status(self):
            return psutil.STATUS_RUNNING

        def terminate(self):
            pass

        def kill(self):
            pass

    fake = FakeProc()
    monkeypatch.setattr(psutil, "Process", lambda pid: fake)
    monkeypatch.setattr(psutil, "wait_procs", lambda procs, timeout: ([], [fake]))
    result = _terminate(4243, force=False)
    assert result["terminated"] is False
    assert "still running" in result["reason"]

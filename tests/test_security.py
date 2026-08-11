"""Tests for the heuristic suspicious-process analysis."""
from services.security_analyzer import SecurityAnalyzer, classify_severity


def _analyze(processes):
    return SecurityAnalyzer().analyze_processes(processes)


def _proc(pid=1000, name="python", exe="/usr/bin/python", cpu=1, mem=1,
          username="alice", ppid=1):
    return {
        "pid": pid, "name": name, "exe": exe,
        "cpu_percent": cpu, "memory_percent": mem,
        "username": username, "ppid": ppid,
    }


def test_normal_process_is_low_risk():
    findings = _analyze([_proc()])
    assert findings == []


def test_suspicious_path_elevates_risk():
    findings = _analyze([_proc(exe="/tmp/evil/binary")])
    assert len(findings) == 1
    f = findings[0]
    assert f.score >= 20
    assert f.severity in ("Moderate", "High", "Critical")
    assert any("temporary" in r.lower() for r in f.reasons)


def test_suspicious_keyword_elevates_risk():
    findings = _analyze([_proc(name="xmrig_miner")])
    assert len(findings) == 1
    assert any("keyword" in r for r in findings[0].reasons)


def test_findings_include_reasons_confidence_evidence():
    findings = _analyze([_proc(exe="/tmp/bad")])
    f = findings[0]
    assert f.reasons
    assert 0 < f.confidence <= 0.9
    assert f.evidence.get("exe") == "/tmp/bad"


def test_high_cpu_elevates_risk():
    findings = _analyze([_proc(cpu=95)])
    assert len(findings) == 1
    assert any("High CPU" in r for r in findings[0].reasons)


def test_classify_severity_bands():
    assert classify_severity(10) == "Low"
    assert classify_severity(25) == "Moderate"
    assert classify_severity(45) == "High"
    assert classify_severity(65) == "Critical"

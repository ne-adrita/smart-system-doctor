"""Tests for the heuristic suspicious-process analysis."""
from services.security_analyzer import SecurityAnalyzer, classify_severity


def _analyze(processes):
    return SecurityAnalyzer().analyze_processes(processes)


def _proc(pid=1000, name="python", exe="/usr/bin/python", cpu=1, mem=1,
          username="alice", ppid=2):
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


def test_findings_include_reasons_strength_evidence():
    findings = _analyze([_proc(exe="/tmp/bad")])
    f = findings[0]
    assert f.reasons
    assert 0 < f.heuristic_strength <= 0.9
    assert f.evidence.get("exe") == "/tmp/bad"


def test_low_resource_suspicious_process_is_covered():
    # A suspicious process that uses almost no CPU/RAM must still be caught by
    # the prefilter (previously only the top-40 processes were scanned).
    processes = [
        _proc(pid=9001, name="python"),
        _proc(pid=9002, name="silent_miner", cpu=0.1, mem=0.2),
    ]
    analyzer = SecurityAnalyzer()
    candidates = analyzer.prefilter_processes(processes)
    assert any(p["pid"] == 9002 for p in candidates)
    findings = analyzer.analyze_processes(processes)
    assert any(f.pid == 9002 for f in findings)


def test_recommendation_is_present():
    findings = _analyze([_proc(exe="/tmp/bad", cpu=95)])
    assert findings
    assert findings[0].recommendation


def test_high_cpu_elevates_risk():
    findings = _analyze([_proc(cpu=95)])
    assert len(findings) == 1
    assert any("High CPU" in r for r in findings[0].reasons)


def test_classify_severity_bands():
    assert classify_severity(10) == "Low"
    assert classify_severity(25) == "Moderate"
    assert classify_severity(45) == "High"
    assert classify_severity(65) == "Critical"

"""Heuristic Suspicious Process and Security Analysis.

This module performs a *heuristic* analysis of running processes and open
ports. It is NOT a malware scanner and must not be described as one. Findings
are reported with a severity, a *heuristic strength* value, explicit reasons,
raw evidence and a recommended action so the user can judge for themselves.

The heuristic strength is normalized evidence strength (a score of 0.9 means
"strong heuristic evidence"), NOT a statistical probability that a process is
malicious.

Suspicion score weights (see ``config.py``):

    Suspicious filename          +15
    Suspicious executable path   +20
    Unexpected network activity  +20
    High CPU                     +10
    High memory                  +10
    Unusual parent process       +15
    Privileged process anomaly   +10

Classification:

    0-19   Low
    20-39  Moderate
    40-59  High
    60+    Critical
"""
import socket

import psutil

from config import Config
from models.schemas import PortInfo, SecurityFinding
from utils.logging_utils import get_logger

logger = get_logger(__name__)

SUSPICIOUS_KEYWORDS = [
    "miner", "keylogger", "spyware", "ransomware", "backdoor", "rootkit",
    "trojan", "malware", "adware", "ratware", "stealer", "coinminer",
]

SUSPICIOUS_PATH_PATTERNS = [
    "/tmp/", "/var/tmp/", "/dev/shm", "/private/tmp/",
    "\\windows\\temp\\", "\\programdata\\", "\\users\\public\\",
    "/downloads/", "\\downloads\\",
]

HIGH_RISK_SERVICES = {"telnet", "ftp", "smb", "rdp", "snmp"}

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "::ffff:127.0.0.1", "localhost", ""}


def classify_severity(score):
    if score >= 60:
        return "Critical"
    if score >= 40:
        return "High"
    if score >= 20:
        return "Moderate"
    return "Low"


class SecurityAnalyzer:
    def __init__(self):
        self._known_service_cache = {}

    # -------------------------------------------------------------
    # Port analysis
    # -------------------------------------------------------------
    def analyze_ports(self):
        """Inspect listening ports from the OS, not a blind connect test.

        Distinguishes loopback listeners (low risk) from externally exposed
        listeners (higher risk). Falls back to a loopback connect test if the
        OS denies network-connection introspection.
        """
        raw = self._raw_listening_connections()
        if raw is None:
            return self._fallback_scan()

        ports = []
        seen = set()
        for conn in raw:
            laddr = conn.get("laddr")
            if not laddr:
                continue
            ip, port = laddr.get("ip"), laddr.get("port")
            if not port:
                continue
            key = (ip, port, conn.get("proto", "tcp"))
            if key in seen:
                continue
            seen.add(key)

            exposed = not _is_loopback(ip)
            pid = conn.get("pid")
            proc_name = self._process_name(pid)
            service = self._service_name(port)
            risk_level, reason = self._port_risk(port, service, exposed)
            ports.append(PortInfo(
                port=port,
                protocol=conn.get("proto", "tcp"),
                local_address=ip or "0.0.0.0",
                pid=pid,
                process_name=proc_name,
                service=service,
                risk_level=risk_level,
                exposed=exposed,
            ))

        ports.sort(key=lambda p: (not p.exposed, p.port))
        return ports

    def _raw_listening_connections(self):
        """Collect listening sockets, tolerating per-process AccessDenied."""
        try:
            conns = psutil.net_connections(kind="inet")
            return self._filter_listening(conns, pid_lookup=False)
        except (psutil.AccessDenied, OSError):
            logger.debug("net_connections denied globally; using per-process scan")
        except Exception:
            logger.debug("net_connections failed; using per-process scan", exc_info=True)

        # Some platforms (macOS) deny connection introspection for specific
        # processes, which aborts the global call. Scan per-process instead.
        result = []
        try:
            procs = psutil.process_iter(["pid"])
        except Exception:
            return None
        for proc in procs:
            try:
                conns = proc.connections(kind="inet")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            result.extend(self._filter_listening(conns, pid_lookup=True, pid=proc.info["pid"]))
        return result or None

    @staticmethod
    def _filter_listening(conns, pid_lookup, pid=None):
        """Keep TCP sockets in LISTEN state only.

        UDP sockets are deliberately excluded: bound UDP ports (often
        ephemeral, e.g. browser traffic) are not "listening services" and
        would flood the analysis with noise.
        """
        result = []
        for c in conns:
            if c.type != socket.SOCK_STREAM or c.status != psutil.CONN_LISTEN:
                continue
            if not c.laddr:
                continue
            result.append({
                "laddr": c.laddr._asdict(),
                "pid": pid if pid_lookup else c.pid,
                "proto": "tcp",
            })
        return result

    def _fallback_scan(self):
        """Last-resort loopback connect test (only reaches 127.0.0.1)."""
        ports = []
        for port in sorted(Config.KNOWN_PORTS.keys()):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.3)
            try:
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    service = Config.KNOWN_PORTS.get(port)
                    risk, _ = self._port_risk(port, service, False)
                    ports.append(PortInfo(
                        port=port, protocol="tcp", local_address="127.0.0.1",
                        pid=None, process_name=None, service=service,
                        risk_level=risk, exposed=False,
                    ))
            finally:
                s.close()
        return ports

    def _service_name(self, port):
        if port in Config.KNOWN_PORTS:
            return Config.KNOWN_PORTS[port]
        if port in self._known_service_cache:
            return self._known_service_cache[port]
        try:
            name = socket.getservbyport(port)
        except OSError:
            name = None
        self._known_service_cache[port] = name
        return name

    def _port_risk(self, port, service, exposed):
        """Risk classification that does not brand common ports as malicious."""
        if not exposed:
            return "Low", "Listening on loopback only - not reachable from the network"
        svc = (service or "").lower()
        if svc in HIGH_RISK_SERVICES:
            return "High", f"Externally exposed service {service or port} is a common attack target"
        if port < 1024:
            return "Moderate", "Privileged port exposed on all interfaces"
        return "Moderate", "Service exposed on all network interfaces"

    def _process_name(self, pid):
        if not pid:
            return None
        try:
            return psutil.Process(pid).name()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None

    # -------------------------------------------------------------
    # Suspicious process analysis (two-stage pipeline)
    # -------------------------------------------------------------
    def analyze_processes(self, processes, connections_map=None):
        """Run the two-stage heuristic analysis.

        Stage 1 - cheap prefilter over *all* processes (no suspicious process
        is skipped simply because it uses little CPU).
        Stage 2 - transparent suspicion scoring for the prefiltered subset.

        ``connections_map`` maps pid -> list of connection dicts (precomputed
        by the caller to bound cost).
        """
        connections_map = connections_map or {}
        candidates = self.prefilter_processes(processes, connections_map)
        findings = []
        for proc in candidates:
            result = self._score_process(proc, connections_map.get(proc["pid"], []))
            if result and result.score > 0:
                findings.append(result)
        findings.sort(key=lambda f: f.score, reverse=True)
        return findings

    def prefilter_processes(self, processes, connections_map=None):
        """Select processes that exhibit at least one cheap suspicious signal.

        Only the returned subset receives detailed scoring, so the scan stays
        cheap while still covering low-resource suspicious processes.
        """
        connections_map = connections_map or {}
        candidates = []
        for proc in processes:
            if self._cheap_signal(proc, connections_map.get(proc["pid"], [])):
                candidates.append(proc)
        return candidates

    @staticmethod
    def _cheap_signal(proc, connections):
        name = (proc.get("name") or "").lower()
        if any(keyword in name for keyword in SUSPICIOUS_KEYWORDS):
            return True

        exe = proc.get("exe") or ""
        if exe:
            lowered = exe.lower()
            if any(pattern in lowered for pattern in SUSPICIOUS_PATH_PATTERNS):
                return True

        if (proc.get("cpu_percent") or 0.0) >= Config.SUSPICIOUS_CPU_PERCENT:
            return True
        if (proc.get("memory_percent") or 0.0) >= Config.SUSPICIOUS_MEMORY_PERCENT:
            return True

        ppid = proc.get("ppid")
        if ppid is None or ppid <= 1:
            return True

        if any(c.get("remote_address") for c in connections):
            return True

        return False

    def _score_process(self, proc, connections):
        pid = proc.get("pid")
        name = proc.get("name") or ""
        exe = proc.get("exe") or ""
        cpu = proc.get("cpu_percent") or 0.0
        memory = proc.get("memory_percent") or 0.0
        username = proc.get("username") or ""
        ppid = proc.get("ppid")

        score = 0
        reasons = []
        evidence = {
            "name": name,
            "exe": exe,
            "cpu": round(cpu, 1),
            "memory_percent": round(memory, 1),
            "memory_rss": proc.get("memory_rss"),
            "username": username,
            "ppid": ppid,
        }

        # 1. Suspicious filename keyword.
        lowered_name = name.lower()
        for keyword in SUSPICIOUS_KEYWORDS:
            if keyword in lowered_name:
                score += Config.WEIGHT_SUSPICIOUS_FILENAME
                reasons.append(f"Process name contains suspicious keyword '{keyword}'")
                evidence["keyword"] = keyword
                break

        # 2. Suspicious executable path.
        if exe:
            lowered_exe = exe.lower()
            for pattern in SUSPICIOUS_PATH_PATTERNS:
                if pattern in lowered_exe:
                    score += Config.WEIGHT_SUSPICIOUS_PATH
                    reasons.append(
                        f"Executable located in a temporary or user-writable directory: {exe}")
                    evidence["suspicious_path"] = exe
                    break

        # 3. Unexpected network activity (outbound established connections).
        outbound = [c for c in connections if c.get("remote_address")]
        if outbound and score >= Config.NETWORK_FLAG_CUTOFF:
            score += Config.WEIGHT_NETWORK_ACTIVITY
            reasons.append(f"Established outbound network connections ({len(outbound)})")
            evidence["connections"] = outbound[:5]

        # 4. High CPU.
        if cpu >= Config.SUSPICIOUS_CPU_PERCENT:
            score += Config.WEIGHT_HIGH_CPU
            reasons.append(f"High CPU usage ({cpu:.1f}%)")

        # 5. High memory.
        if memory >= Config.SUSPICIOUS_MEMORY_PERCENT:
            score += Config.WEIGHT_HIGH_MEMORY
            reasons.append(f"High memory usage ({memory:.1f}%)")

        # 6. Unusual parent relationship.
        if ppid is None or ppid <= 1:
            if score > 0:
                score += Config.WEIGHT_UNUSUAL_PARENT
                reasons.append(f"Orphaned or parentless process (parent PID {ppid})")
                evidence["unusual_parent"] = ppid

        # 7. Privileged process anomaly.
        if username in ("root", "SYSTEM") and exe and any(
            p in exe.lower() for p in SUSPICIOUS_PATH_PATTERNS
        ):
            score += Config.WEIGHT_PRIVILEGED_ANOMALY
            reasons.append("Privileged process running from an unusual location")
            evidence["privileged"] = True

        if score == 0:
            return None

        return SecurityFinding(
            pid=pid,
            name=name or f"PID {pid}",
            severity=classify_severity(score),
            heuristic_strength=round(min(Config.HEURISTIC_STRENGTH_CEILING, score / 100.0), 2),
            score=score,
            reasons=reasons,
            evidence=evidence,
            recommendation=_build_recommendation(name, pid, reasons),
        )

    # -------------------------------------------------------------
    # Aggregate security score
    # -------------------------------------------------------------
    def security_score(self, findings, ports):
        """0-100 security posture score derived from findings + exposed ports."""
        score = 100
        reasons = []

        for finding in findings:
            severity = finding.severity
            penalty = {"Critical": 40, "High": 25, "Moderate": 15, "Low": 10}[severity]
            score -= penalty
            reasons.append(
                f"{severity.lower()} suspicion: {finding.name} (score {finding.score})"
            )

        exposed = [p for p in ports if p.exposed]
        if exposed:
            score -= min(30, 5 * len(exposed))
            reasons.append(f"{len(exposed)} service(s) listening on all interfaces")

        score = max(0, score)
        if score >= 80:
            status, color = "Safe", "green"
        elif score >= 60:
            status, color = "Caution", "yellow"
        else:
            status, color = "Risky", "red"

        return {
            "score": score,
            "status": status,
            "color": color,
            "reasons": reasons,
        }


def _build_recommendation(name, pid, reasons):
    """Construct a human-readable recommended action for a finding."""
    recs = [f"Inspect process '{name}' (PID {pid})"]
    joined = " ".join(reasons).lower()
    if "network" in joined:
        recs.append("verify its outbound network destinations")
    if "directory" in joined or "location" in joined:
        recs.append("confirm the executable location is legitimate")
    if "cpu" in joined or "memory" in joined:
        recs.append("check whether its resource usage is expected")
    return ". ".join(recs) + "."


def _is_loopback(ip):
    if not ip:
        return True
    if ip in LOOPBACK_HOSTS:
        return True
    return ip.startswith("127.")

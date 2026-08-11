"""Smart System Doctor Pro - Flask application.

REST-style API backed by a service layer. Expensive operations (security
scan, port scan, database logging) run in a background worker so the fast
metrics endpoint stays responsive.
"""
import gc
import os
import threading
import time

import psutil
from flask import Flask, jsonify, render_template, request, send_file

from config import get_config
from database import (
    get_history,
    get_recent_recommendations,
    get_recent_security_events,
    get_statistics,
    init_db,
    prune_history,
    record_port_event,
    record_process_snapshot,
    record_recommendation,
    record_security_event,
    record_system_metrics,
)
from models.schemas import ApiError, ApiResponse
from services import process_monitor, recommendation_service
from services.health_analyzer import compute_health_score
from services.prediction_service import get_predictions
from services.report_service import generate_report
from services.security_analyzer import SecurityAnalyzer
from services.system_monitor import (
    get_cpu,
    get_cpu_info,
    get_disk,
    get_disk_io,
    get_memory,
    get_network,
    get_os_info,
    get_process_count,
    get_swap,
    get_uptime,
)
from utils.logging_utils import get_logger
from utils.process_utils import terminate_process
from utils.system_utils import format_bytes

config = get_config()
logger = get_logger(__name__)

security_analyzer = SecurityAnalyzer()


class SnapshotCache:
    """Thread-safe holder for the latest computed snapshot values."""

    def __init__(self):
        self.lock = threading.Lock()
        self.cpu = 0.0
        self.ram = 0.0
        self.disk_percent = 0.0
        self.disk = {}
        self.network = {}
        self.process_count = 0
        self.uptime = {}
        self.os = {}
        self.cpu_info = {}
        self.memory = {}
        self.swap = {}
        self.disk_io = {}
        self.findings = []
        self.ports = []
        self.security = {"score": 100, "status": "Safe", "color": "green", "reasons": []}
        self.last_security_scan = None
        self.last_port_scan = None
        self.last_history_write = None

    def update(self, **kwargs):
        with self.lock:
            for key, value in kwargs.items():
                setattr(self, key, value)

    def snapshot(self, **overrides):
        with self.lock:
            data = {
                "cpu": self.cpu,
                "ram": self.ram,
                "disk": self.disk,
                "disk_percent": self.disk_percent,
                "network": self.network,
                "process_count": self.process_count,
                "uptime": self.uptime,
                "os": self.os,
                "cpu_info": self.cpu_info,
                "memory": self.memory,
                "swap": self.swap,
                "disk_io": self.disk_io,
                "findings": self.findings,
                "ports": self.ports,
                "security": self.security,
                "last_security_scan": self.last_security_scan,
                "last_port_scan": self.last_port_scan,
                "last_history_write": self.last_history_write,
            }
            data.update(overrides)
            return data


cache = SnapshotCache()


class BackgroundWorker:
    """Runs expensive monitoring tasks on a schedule, off the request path."""

    def __init__(self):
        self._stop = threading.Event()
        self._last_recs_hash = None

    def stop(self):
        self._stop.set()

    def _update_moderate_metrics(self):
        memory = get_memory()
        disk = get_disk()
        cache.update(
            cpu=get_cpu(),
            ram=memory["percent"],
            disk=disk,
            disk_percent=disk["percent"],
            network=get_network(),
            process_count=get_process_count(),
            uptime=get_uptime(),
            os=get_os_info(),
            cpu_info=get_cpu_info(),
            memory=memory,
            swap=get_swap(),
            disk_io=get_disk_io(),
        )

    def _write_history(self):
        snap = cache.snapshot()
        cpu = get_cpu()
        health = compute_health_score(
            cpu, snap["ram"], snap["disk_percent"], snap["process_count"], snap["network"]
        )
        record_system_metrics(
            cpu=cpu,
            ram=snap["ram"],
            disk=snap["disk_percent"],
            net_sent=snap["network"].get("bytes_sent", 0),
            net_recv=snap["network"].get("bytes_recv", 0),
            process_count=snap["process_count"],
            health_score=health.score,
            security_score=snap["security"]["score"],
        )
        cache.update(last_history_write=time.strftime("%Y-%m-%d %H:%M:%S"))

        # Persist recommendations only when they change to bound DB growth.
        predictions = get_predictions(hours=1)
        recs = recommendation_service.build_recommendations(
            health, {"score": snap["security"]["score"],
                     "ports": snap["ports"]}, snap["disk_percent"], predictions
        )
        recs_hash = hash(tuple((r["title"], r["severity"]) for r in recs))
        if recs_hash != self._last_recs_hash:
            self._last_recs_hash = recs_hash
            for r in recs:
                record_recommendation(r["severity"], r["title"],
                                      r["description"], r["action"])

    def _scan_ports(self):
        ports = security_analyzer.analyze_ports()
        cache.update(ports=ports, last_port_scan=time.strftime("%Y-%m-%d %H:%M:%S"))
        try:
            for p in ports:
                record_port_event(p.port, p.protocol, p.local_address, p.pid,
                                  p.process_name, p.service, p.risk_level)
        except Exception:
            logger.warning("Failed to persist port events", exc_info=True)

    def _scan_security(self):
        snap = cache.snapshot()
        top = process_monitor.get_processes(sort_by="cpu", limit=0)[:40]
        top.sort(key=lambda p: (p["cpu_percent"] or 0) + (p["memory_percent"] or 0),
                 reverse=True)
        top = top[:40]

        connections_map = _build_connections_map()
        enriched = []
        for proc in top:
            row = _enrich_process(proc)
            if row:
                row["connections"] = connections_map.get(proc["pid"], [])
                enriched.append(row)

        findings = security_analyzer.analyze_processes(enriched)
        security = security_analyzer.security_score(findings, snap["ports"])
        cache.update(
            findings=[f.to_dict() for f in findings],
            security=security,
            last_security_scan=time.strftime("%Y-%m-%d %H:%M:%S"),
        )
        try:
            for f in findings:
                record_security_event(f.to_dict())
                record_process_snapshot(
                    pid=f.pid, name=f.name,
                    cpu_percent=f.evidence.get("cpu"),
                    memory_percent=f.evidence.get("memory_percent"),
                    memory_rss=0, username=f.evidence.get("username"),
                    exe=f.evidence.get("exe"), status=None,
                )
        except Exception:
            logger.warning("Failed to persist security events", exc_info=True)

    def run(self):
        last_moderate = last_history = last_security = last_ports = 0.0
        while not self._stop.is_set():
            now = time.monotonic()
            try:
                if now - last_moderate >= config.DISK_NETWORK_INTERVAL:
                    self._update_moderate_metrics()
                    last_moderate = now
                if now - last_history >= config.HISTORY_INTERVAL:
                    self._write_history()
                    last_history = now
                if now - last_ports >= config.PORT_SCAN_INTERVAL:
                    self._scan_ports()
                    last_ports = now
                if now - last_security >= config.SECURITY_SCAN_INTERVAL:
                    self._scan_security()
                    last_security = now
                if now - last_moderate >= 3600:
                    try:
                        prune_history()
                    except Exception:
                        logger.warning("prune_history failed", exc_info=True)
            except Exception:
                logger.exception("Background worker error")
            self._stop.wait(1.0)


def _build_connections_map():
    """Group established outbound connections by owning PID (one psutil call)."""
    mapping = {}
    try:
        conns = psutil.net_connections(kind="inet")
    except (psutil.AccessDenied, OSError):
        logger.debug("net_connections unavailable for security scan", exc_info=True)
        return mapping
    for c in conns:
        if c.type != psutil.SOCK_STREAM or c.status != psutil.CONN_ESTABLISHED:
            continue
        if not c.raddr or not c.pid:
            continue
        entry = {"remote_address": f"{c.raddr.ip}:{c.raddr.port}"}
        mapping.setdefault(c.pid, []).append(entry)
    return mapping


def _enrich_process(proc):
    pid = proc["pid"]
    try:
        p = psutil.Process(pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None
    try:
        exe = p.exe()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        exe = None
    try:
        username = p.username()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        username = None
    return {
        "pid": pid,
        "name": proc["name"],
        "exe": exe,
        "username": username,
        "cpu_percent": proc["cpu_percent"],
        "memory_percent": proc["memory_percent"],
        "ppid": proc["ppid"],
    }


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------
def ok(data):
    return jsonify(ApiResponse(success=True, data=data).to_dict())


def fail(code, message, status=400):
    return jsonify(ApiResponse(success=False, error=ApiError(code, message)).to_dict()), status


def _downsample(rows, max_points=config.DOWNLOAD_POINTS):
    if len(rows) <= max_points:
        return rows
    step = len(rows) / max_points
    return [rows[int(i * step)] for i in range(max_points)]


def create_app():
    app = Flask(__name__)
    app.config["DEBUG"] = config.FLASK_DEBUG
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["JSON_SORT_KEYS"] = False

    init_db()

    # Start the background worker unless we are in a test configuration.
    if not getattr(config, "DISABLE_BACKGROUND", False):
        start_background_worker()

    # ----------------------------------------------------------------
    # Fast metrics / overview
    # ----------------------------------------------------------------
    @app.route("/")
    def home():
        return render_template("index.html")

    @app.route("/api/system")
    def api_system():
        # CPU and RAM are cheap enough to compute live; heavier metrics cached.
        snap = cache.snapshot()
        return ok({
            "cpu": get_cpu(),
            "memory": get_memory(),
            "disk": snap["disk"],
            "disk_percent": snap["disk_percent"],
            "network": snap["network"],
            "process_count": snap["process_count"],
            "uptime": snap["uptime"],
            "os": snap["os"],
            "cpu_info": snap["cpu_info"],
            "swap": snap["swap"],
            "disk_io": snap["disk_io"],
            "last_update": time.strftime("%Y-%m-%d %H:%M:%S"),
        })

    @app.route("/api/health")
    def api_health():
        snap = cache.snapshot()
        cpu = get_cpu()
        health = compute_health_score(
            cpu, snap["ram"], snap["disk_percent"], snap["process_count"], snap["network"]
        )
        return ok(health.to_dict())

    @app.route("/api/security")
    def api_security():
        snap = cache.snapshot()
        return ok({
            "score": snap["security"]["score"],
            "status": snap["security"]["status"],
            "color": snap["security"]["color"],
            "reasons": snap["security"]["reasons"],
            "findings": snap["findings"],
            "ports": [p.to_dict() for p in snap["ports"]],
            "last_scan": snap["last_security_scan"],
            "disclaimer": "Heuristic analysis only - not a malware scanner.",
        })

    # ----------------------------------------------------------------
    # Processes
    # ----------------------------------------------------------------
    @app.route("/api/processes")
    def api_processes():
        sort_by = request.args.get("sort_by", "cpu")
        order = request.args.get("order", "desc")
        limit = request.args.get("limit", 50, type=int)
        filter_ = request.args.get("filter", "all")
        processes = process_monitor.get_processes(
            sort_by=sort_by, order=order, limit=limit, filter_=filter_
        )
        return ok({"processes": processes, "count": len(processes)})

    @app.route("/api/processes/<int:pid>")
    def api_process_details(pid):
        try:
            details = process_monitor.get_process_details(pid)
        except psutil.NoSuchProcess:
            return fail("PROCESS_NOT_FOUND", "The process no longer exists.", 404)
        except (psutil.AccessDenied, psutil.ZombieProcess):
            return fail("PROCESS_ACCESS_DENIED", "Access to the process was denied.", 403)
        return ok(details)

    @app.route("/api/processes/<int:pid>/terminate", methods=["POST"])
    def api_terminate(pid):
        return _terminate_impl(pid, force=False)

    @app.route("/api/processes/<int:pid>/kill", methods=["POST"])
    def api_kill(pid):
        return _terminate_impl(pid, force=True)

    def _terminate_impl(pid, force):
        try:
            result = terminate_process(pid, force=force)
        except ValueError as exc:
            return fail("INVALID_PID", str(exc), 400)
        except PermissionError as exc:
            return fail("PROTECTED_PROCESS", str(exc), 403)
        except psutil.NoSuchProcess:
            return fail("PROCESS_NOT_FOUND", "The process no longer exists.", 404)
        except psutil.AccessDenied:
            return fail("ACCESS_DENIED", "Insufficient privileges to terminate this process.", 403)
        except Exception:
            logger.exception("Terminate failed for pid %s", pid)
            return fail("TERMINATE_FAILED", "An unexpected error occurred.", 500)
        return ok({
            "terminated": result["terminated"],
            "message": "Process terminated successfully" if result["terminated"]
                       else result["reason"],
            "details": result["details"],
        })

    # ----------------------------------------------------------------
    # Ports
    # ----------------------------------------------------------------
    @app.route("/api/ports")
    def api_ports():
        snap = cache.snapshot()
        exposed = [p for p in snap["ports"] if p.exposed]
        return ok({
            "ports": [p.to_dict() for p in snap["ports"]],
            "exposed_count": len(exposed),
            "last_scan": snap["last_port_scan"],
        })

    # ----------------------------------------------------------------
    # History / statistics / predictions
    # ----------------------------------------------------------------
    @app.route("/api/history")
    def api_history():
        hours = request.args.get("hours", type=int)
        limit = request.args.get("limit", config.MAX_HISTORY_POINTS, type=int)
        history = _downsample(get_history(hours=hours, limit=limit))
        return ok({"history": history, "count": len(history)})

    @app.route("/api/statistics")
    def api_statistics():
        return ok(get_statistics())

    @app.route("/api/predictions")
    def api_predictions():
        hours = request.args.get("hours", 2, type=int)
        predictions = get_predictions(hours=hours)
        return ok(predictions)

    # ----------------------------------------------------------------
    # Recommendations
    # ----------------------------------------------------------------
    @app.route("/api/recommendations")
    def api_recommendations():
        snap = cache.snapshot()
        cpu = get_cpu()
        health = compute_health_score(
            cpu, snap["ram"], snap["disk_percent"], snap["process_count"], snap["network"]
        )
        predictions = get_predictions(hours=1)
        recs = recommendation_service.build_recommendations(
            health, {"score": snap["security"]["score"], "ports": snap["ports"]},
            snap["disk_percent"], predictions,
        )
        return ok({"recommendations": recs, "count": len(recs)})

    @app.route("/api/events")
    def api_events():
        return ok({
            "security_events": get_recent_security_events(limit=20),
            "recommendations": get_recent_recommendations(limit=20),
        })

    # ----------------------------------------------------------------
    # Maintenance (honest garbage collection - no fake memory freeing)
    # ----------------------------------------------------------------
    @app.route("/api/maintenance/gc", methods=["POST"])
    def api_gc():
        before = _rss_bytes()
        collected = gc.collect()
        after = _rss_bytes()
        return ok({
            "message": "Application garbage collection completed",
            "objects_collected": collected,
            "python_heap_before_bytes": before,
            "python_heap_after_bytes": after,
            "note": "This releases Python-internal objects and does not "
                    "necessarily free OS-level RAM.",
        })

    # ----------------------------------------------------------------
    # PDF report
    # ----------------------------------------------------------------
    @app.route("/api/reports/pdf", methods=["POST"])
    def api_report():
        try:
            snap = cache.snapshot()
            cpu = get_cpu()
            health = compute_health_score(
                cpu, snap["ram"], snap["disk_percent"], snap["process_count"],
                snap["network"],
            )
            predictions = get_predictions(hours=2)
            recs = recommendation_service.build_recommendations(
                health, {"score": snap["security"]["score"], "ports": snap["ports"]},
                snap["disk_percent"], predictions,
            )
            history = _downsample(get_history(hours=24, limit=200))

            report_data = {
                "cpu": cpu,
                "ram": snap["ram"],
                "disk": snap["disk"],
                "disk_percent": snap["disk_percent"],
                "memory": snap["memory"],
                "network": snap["network"],
                "process_count": snap["process_count"],
                "cpu_info": snap["cpu_info"],
                "os": snap["os"],
                "uptime": snap["uptime"],
                "health": health.to_dict(),
                "security": snap["security"],
                "findings": snap["findings"],
                "ports": [p.to_dict() for p in snap["ports"]],
                "suspicious_count": len(snap["findings"]),
                "history": history,
                "predictions": predictions,
                "recommendations": recs,
            }
            path = generate_report(report_data)
            return send_file(path, as_attachment=True,
                             download_name=os.path.basename(path))
        except Exception:
            logger.exception("Report generation failed")
            return fail("REPORT_FAILED", "Failed to generate the PDF report.", 500)

    # ----------------------------------------------------------------
    # Legacy compatibility aliases
    # ----------------------------------------------------------------
    @app.route("/history")
    def legacy_history():
        limit = request.args.get("limit", 50, type=int)
        return ok({"data": get_history(limit=limit)})

    @app.route("/statistics")
    def legacy_statistics():
        return ok(get_statistics())

    @app.route("/system-info")
    def legacy_system_info():
        snap = cache.snapshot()
        return ok({
            "cpu_count": snap["cpu_info"].get("count"),
            "cpu_freq": snap["cpu_info"],
            "total_ram": snap["memory"].get("total"),
            "total_disk": snap["disk"].get("total"),
            "boot_time": snap["uptime"].get("boot_time_iso"),
            "os": snap["os"].get("os_name"),
            "platform": snap["os"].get("system"),
        })

    @app.route("/process/<int:pid>")
    def legacy_process_details(pid):
        try:
            details = process_monitor.get_process_details(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return fail("PROCESS_NOT_FOUND", "The process no longer exists.", 404)
        return ok(details)

    # ----------------------------------------------------------------
    # Error handlers
    # ----------------------------------------------------------------
    @app.errorhandler(404)
    def not_found(_):
        return fail("NOT_FOUND", "Endpoint not found.", 404)

    @app.errorhandler(500)
    def server_error(_):
        return fail("INTERNAL_ERROR", "An internal error occurred.", 500)

    return app


def _rss_bytes():
    try:
        proc = psutil.Process()
        mem = proc.memory_info()
        return mem.rss
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
_worker = None


def start_background_worker():
    """Start the scheduled background worker if it is not already running."""
    global _worker
    if _worker is not None:
        return _worker
    _worker = BackgroundWorker()
    thread = threading.Thread(target=_worker.run, name="ssd-worker", daemon=True)
    thread.start()
    logger.info("Background worker started")
    return _worker


app = create_app()


if __name__ == "__main__":
    start_background_worker()
    logger.info("Smart System Doctor Pro starting on %s:%s (debug=%s)",
                config.FLASK_HOST, config.FLASK_PORT, config.FLASK_DEBUG)
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT,
            debug=config.FLASK_DEBUG)

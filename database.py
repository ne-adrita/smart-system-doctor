"""SQLite persistence layer.

Schema:
    system_metrics    -- periodic history of core metrics
    process_snapshots -- snapshots of notable / suspicious processes
    security_events   -- heuristic security findings
    port_events       -- observed listening ports
    recommendations   -- rule-based recommendations emitted over time

The connection is opened per operation (SQLite is cheap for local use) and
``WAL`` mode plus indexes keep concurrent reads cheap.
"""
import json
import sqlite3
import threading
from datetime import datetime, timedelta

from config import get_config

Config = get_config()

_local = threading.local()


def _connect():
    conn = sqlite3.connect(Config.DATABASE_PATH, timeout=Config.DB_TIMEOUT)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def get_conn():
    """Thread-local connection so each request thread reuses one handle."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _connect()
        _local.conn = conn
    return conn


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS system_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            cpu REAL,
            ram REAL,
            disk REAL,
            network_bytes_sent INTEGER,
            network_bytes_recv INTEGER,
            process_count INTEGER,
            health_score REAL,
            security_score REAL
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS process_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            pid INTEGER,
            name TEXT,
            cpu_percent REAL,
            memory_percent REAL,
            memory_rss INTEGER,
            username TEXT,
            exe TEXT,
            status TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS security_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            pid INTEGER,
            name TEXT,
            severity TEXT,
            heuristic_strength REAL,
            score INTEGER,
            reasons TEXT,
            evidence TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS port_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            port INTEGER,
            protocol TEXT,
            local_address TEXT,
            pid INTEGER,
            process_name TEXT,
            service TEXT,
            risk_level TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            severity TEXT,
            title TEXT,
            description TEXT,
            action TEXT
        )
        """
    )

    c.execute("CREATE INDEX IF NOT EXISTS idx_metrics_time ON system_metrics(timestamp)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_security_time ON security_events(timestamp)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ports_time ON port_events(timestamp)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_recommendations_time ON recommendations(timestamp)")

    # Migration: v4.0 -> v4.0.1 renamed the security finding measure from
    # "confidence" to the more accurate "heuristic_strength".
    cols = [row[1] for row in c.execute("PRAGMA table_info(security_events)").fetchall()]
    if "heuristic_strength" not in cols and "confidence" in cols:
        c.execute("ALTER TABLE security_events RENAME COLUMN confidence TO heuristic_strength")

    conn.commit()


def record_system_metrics(cpu, ram, disk, net_sent, net_recv, process_count,
                          health_score, security_score):
    get_conn().execute(
        """
        INSERT INTO system_metrics
            (timestamp, cpu, ram, disk, network_bytes_sent, network_bytes_recv,
             process_count, health_score, security_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (_now(), cpu, ram, disk, net_sent, net_recv, process_count,
         health_score, security_score),
    )
    get_conn().commit()


def record_process_snapshot(pid, name, cpu_percent, memory_percent, memory_rss,
                            username, exe, status):
    get_conn().execute(
        """
        INSERT INTO process_snapshots
            (timestamp, pid, name, cpu_percent, memory_percent, memory_rss,
             username, exe, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (_now(), pid, name, cpu_percent, memory_percent, memory_rss,
         username, exe, status),
    )
    get_conn().commit()


def record_security_event(finding):
    get_conn().execute(
        """
        INSERT INTO security_events
            (timestamp, pid, name, severity, heuristic_strength, score, reasons, evidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (_now(), finding.get("pid"), finding.get("name"), finding.get("severity"),
         finding.get("heuristic_strength"), finding.get("score"),
         json.dumps(finding.get("reasons", [])),
         json.dumps(finding.get("evidence", {}), default=str)),
    )
    get_conn().commit()


def record_port_event(port, protocol, local_address, pid, process_name, service, risk_level):
    get_conn().execute(
        """
        INSERT INTO port_events (timestamp, port, protocol, local_address, pid,
                                 process_name, service, risk_level)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (_now(), port, protocol, local_address, pid, process_name, service, risk_level),
    )
    get_conn().commit()


def record_recommendation(severity, title, description, action):
    get_conn().execute(
        """
        INSERT INTO recommendations (timestamp, severity, title, description, action)
        VALUES (?, ?, ?, ?, ?)
        """,
        (_now(), severity, title, description, action),
    )
    get_conn().commit()


def _rows_to_history(rows):
    return [
        {
            "time": row["timestamp"],
            "cpu": row["cpu"],
            "ram": row["ram"],
            "disk": row["disk"],
            "health": row["health_score"],
            "security": row["security_score"],
            "processes": row["process_count"],
        }
        for row in rows
    ]


def get_history(hours=None, limit=Config.MAX_HISTORY_POINTS):
    """Return chronological history rows. ``hours`` filters by age."""
    inner = "SELECT * FROM system_metrics"
    params = []
    if hours:
        cutoff = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        inner += " WHERE timestamp >= ?"
        params.append(cutoff)
    if limit:
        # Latest `limit` rows, returned chronologically ascending.
        inner += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
    sql = f"SELECT * FROM ({inner}) ORDER BY id ASC"
    rows = get_conn().execute(sql, params).fetchall()
    return _rows_to_history(rows)


def get_statistics():
    c = get_conn().cursor()
    c.execute(
        """
        SELECT
            COUNT(*) as total_records,
            AVG(cpu) as avg_cpu, MAX(cpu) as max_cpu, MIN(cpu) as min_cpu,
            AVG(ram) as avg_ram, MAX(ram) as max_ram, MIN(ram) as min_ram,
            AVG(disk) as avg_disk, MAX(disk) as max_disk, MIN(disk) as min_disk,
            AVG(health_score) as avg_health,
            AVG(security_score) as avg_security
        FROM system_metrics
        """
    )
    row = c.fetchone()
    if not row or not row["total_records"]:
        return {}
    return {
        "total_records": row["total_records"],
        "avg_cpu": round(row["avg_cpu"], 2),
        "max_cpu": round(row["max_cpu"], 2),
        "min_cpu": round(row["min_cpu"], 2),
        "avg_ram": round(row["avg_ram"], 2),
        "max_ram": round(row["max_ram"], 2),
        "min_ram": round(row["min_ram"], 2),
        "avg_disk": round(row["avg_disk"], 2),
        "max_disk": round(row["max_disk"], 2),
        "min_disk": round(row["min_disk"], 2),
        "avg_health": round(row["avg_health"], 2),
        "avg_security": round(row["avg_security"], 2),
    }


def get_recent_security_events(limit=20):
    rows = get_conn().execute(
        """
        SELECT * FROM security_events ORDER BY id DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [
        {
            "pid": r["pid"],
            "name": r["name"],
            "severity": r["severity"],
            "heuristic_strength": r["heuristic_strength"],
            "score": r["score"],
            "reasons": json.loads(r["reasons"] or "[]"),
            "evidence": json.loads(r["evidence"] or "{}"),
            "timestamp": r["timestamp"],
        }
        for r in rows
    ]


def get_recent_port_events(limit=50):
    rows = get_conn().execute(
        """
        SELECT * FROM port_events ORDER BY id DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [
        {
            "port": r["port"],
            "protocol": r["protocol"],
            "local_address": r["local_address"],
            "pid": r["pid"],
            "process_name": r["process_name"],
            "service": r["service"],
            "risk_level": r["risk_level"],
        }
        for r in rows
    ]


def get_recent_recommendations(limit=20):
    rows = get_conn().execute(
        """
        SELECT * FROM recommendations ORDER BY id DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [
        {
            "severity": r["severity"],
            "title": r["title"],
            "description": r["description"],
            "action": r["action"],
            "timestamp": r["timestamp"],
        }
        for r in rows
    ]


def prune_history():
    """Delete rows older than the retention window to bound database growth."""
    cutoff = (datetime.now() - timedelta(days=Config.HISTORY_RETENTION_DAYS)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    for table in ("system_metrics", "security_events", "port_events", "recommendations"):
        get_conn().execute(f"DELETE FROM {table} WHERE timestamp < ?", (cutoff,))
    get_conn().commit()

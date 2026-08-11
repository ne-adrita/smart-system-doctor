"""Database integrity tests: schema creation, insert/retrieve, retention."""
from datetime import datetime, timedelta

from config import Config
from database import (
    get_conn,
    get_history,
    get_recent_security_events,
    init_db,
    prune_history,
    record_security_event,
    record_system_metrics,
)

_TABLES = ("system_metrics", "process_snapshots", "security_events",
           "port_events", "recommendations")


def _table_names():
    rows = get_conn().execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {row["name"] for row in rows}


def test_init_creates_all_tables():
    init_db()
    names = _table_names()
    for table in _TABLES:
        assert table in names


def test_insert_and_retrieve_metrics():
    init_db()
    get_conn().execute("DELETE FROM system_metrics")
    get_conn().commit()
    record_system_metrics(cpu=42.5, ram=63.1, disk=55.0, net_sent=10,
                          net_recv=20, process_count=123, health_score=88,
                          security_score=77)
    history = get_history(limit=10)
    assert len(history) >= 1
    row = history[-1]
    assert row["cpu"] == 42.5
    assert row["ram"] == 63.1
    assert row["health"] == 88
    assert row["security"] == 77


def test_record_and_retrieve_security_event():
    init_db()
    get_conn().execute("DELETE FROM security_events")
    get_conn().commit()
    record_security_event({
        "pid": 4321,
        "name": "demo",
        "severity": "Moderate",
        "heuristic_strength": 0.35,
        "score": 25,
        "reasons": ["Unusual location"],
        "evidence": {"exe": "/tmp/x"},
    })
    events = get_recent_security_events(limit=10)
    assert events
    latest = events[0]
    assert latest["pid"] == 4321
    assert latest["heuristic_strength"] == 0.35
    assert latest["reasons"] == ["Unusual location"]
    assert latest["evidence"] == {"exe": "/tmp/x"}


def test_history_hours_filter_respects_cutoff():
    init_db()
    get_conn().execute("DELETE FROM system_metrics")
    old = (datetime.now() - timedelta(hours=50)).strftime("%Y-%m-%d %H:%M:%S")
    get_conn().execute(
        """
        INSERT INTO system_metrics
            (timestamp, cpu, ram, disk, network_bytes_sent, network_bytes_recv,
             process_count, health_score, security_score)
        VALUES (?, 10, 10, 10, 0, 0, 10, 90, 90)
        """,
        (old,),
    )
    record_system_metrics(cpu=30, ram=30, disk=30, net_sent=0, net_recv=0,
                          process_count=10, health_score=90, security_score=90)
    get_conn().commit()

    recent = get_history(hours=2)
    assert all(
        datetime.strptime(r["time"], "%Y-%m-%d %H:%M:%S")
        >= datetime.now() - timedelta(hours=2)
        for r in recent
    )
    assert any(r["cpu"] == 30 for r in recent)
    assert not any(r["cpu"] == 10 for r in recent)


def test_retention_respects_days():
    init_db()
    get_conn().execute("DELETE FROM system_metrics")
    get_conn().commit()
    old = (datetime.now() - timedelta(days=Config.HISTORY_RETENTION_DAYS + 5)
           ).strftime("%Y-%m-%d %H:%M:%S")
    get_conn().execute(
        """
        INSERT INTO system_metrics
            (timestamp, cpu, ram, disk, network_bytes_sent, network_bytes_recv,
             process_count, health_score, security_score)
        VALUES (?, 1, 1, 1, 0, 0, 1, 90, 90)
        """,
        (old,),
    )
    record_system_metrics(cpu=20, ram=20, disk=20, net_sent=0, net_recv=0,
                          process_count=5, health_score=90, security_score=90)
    get_conn().commit()

    prune_history()
    rows = get_history(hours=24 * (Config.HISTORY_RETENTION_DAYS + 10), limit=1000)
    assert any(r["cpu"] == 20 for r in rows)
    assert not any(r["cpu"] == 1 for r in rows)

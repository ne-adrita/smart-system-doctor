"""Regression tests for history pruning.

The background worker must prune old rows on an independent timer so that
frequent "moderate metrics" updates can never starve the daily maintenance
task (previously pruning shared the moderate-metrics timer and effectively
never ran).
"""
from datetime import datetime, timedelta

from config import Config
from database import get_conn, init_db, prune_history, record_system_metrics

_RETENTION = timedelta(days=Config.HISTORY_RETENTION_DAYS + 10)


def _clear_metrics():
    get_conn().execute("DELETE FROM system_metrics")
    get_conn().commit()


def _insert_metrics(ts):
    get_conn().execute(
        """
        INSERT INTO system_metrics
            (timestamp, cpu, ram, disk, network_bytes_sent, network_bytes_recv,
             process_count, health_score, security_score)
        VALUES (?, 1, 1, 1, 0, 0, 1, 90, 90)
        """,
        (ts,),
    )
    get_conn().commit()


def test_prune_removes_old_rows():
    init_db()
    _clear_metrics()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    old = (datetime.now() - _RETENTION).strftime("%Y-%m-%d %H:%M:%S")
    _insert_metrics(now)
    _insert_metrics(old)

    count_before = get_conn().execute("SELECT COUNT(*) FROM system_metrics").fetchone()[0]
    assert count_before == 2

    prune_history()

    remaining = get_conn().execute("SELECT COUNT(*) FROM system_metrics").fetchone()[0]
    assert remaining == 1


def test_prune_keeps_recent_rows():
    init_db()
    _clear_metrics()
    recent = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    _insert_metrics(recent)
    prune_history()
    remaining = get_conn().execute("SELECT COUNT(*) FROM system_metrics").fetchone()[0]
    assert remaining == 1

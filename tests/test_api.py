"""API integration tests using Flask's test client."""
import pytest

import app as app_module


@pytest.fixture()
def client():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def _get(client, url):
    res = client.get(url)
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    assert body["error"] is None
    return body["data"]


def test_home_page(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "Smart System Doctor" in res.get_data(as_text=True)


def test_system_endpoint(client):
    data = _get(client, "/api/system")
    assert "cpu" in data
    assert "memory" in data
    assert "disk" in data
    assert "process_count" in data


def test_health_endpoint(client):
    data = _get(client, "/api/health")
    assert 0 <= data["score"] <= 100
    assert data["status"] in ("Critical", "Poor", "Fair", "Good", "Excellent")
    assert isinstance(data["factors"], list)


def test_security_endpoint(client):
    data = _get(client, "/api/security")
    assert 0 <= data["score"] <= 100
    assert isinstance(data["findings"], list)
    assert "disclaimer" in data


def test_processes_endpoint(client):
    data = _get(client, "/api/processes?limit=10")
    assert isinstance(data["processes"], list)
    for p in data["processes"]:
        assert "pid" in p
        assert "name" in p


def test_processes_sort(client):
    by_cpu = _get(client, "/api/processes?sort_by=cpu&limit=20")
    cpus = [p["cpu_percent"] for p in by_cpu["processes"]]
    assert cpus == sorted(cpus, reverse=True)


def test_history_endpoint(client):
    data = _get(client, "/api/history")
    assert isinstance(data["history"], list)


def test_statistics_endpoint(client):
    data = _get(client, "/api/statistics")
    assert isinstance(data, dict)


def test_predictions_endpoint(client):
    data = _get(client, "/api/predictions")
    assert "available" in data


def test_recommendations_endpoint(client):
    data = _get(client, "/api/recommendations")
    assert isinstance(data["recommendations"], list)


def test_invalid_pid_details(client):
    res = client.get("/api/processes/99999999")
    body = res.get_json()
    assert res.status_code == 404
    assert body["success"] is False
    assert body["error"]["code"] == "PROCESS_NOT_FOUND"


def test_terminate_invalid_pid(client):
    res = client.post("/api/processes/99999999/terminate")
    body = res.get_json()
    assert res.status_code == 404
    assert body["error"]["code"] == "PROCESS_NOT_FOUND"


def test_kill_invalid_pid(client):
    res = client.post("/api/processes/99999999/kill")
    body = res.get_json()
    assert res.status_code == 404
    assert body["error"]["code"] == "PROCESS_NOT_FOUND"


def test_terminate_protected_process(client):
    # PID 1 is always protected.
    res = client.post("/api/processes/1/terminate")
    body = res.get_json()
    assert res.status_code == 403
    assert body["error"]["code"] == "PROTECTED_PROCESS"


def test_unknown_route_returns_envelope(client):
    res = client.get("/api/nonexistent")
    body = res.get_json()
    assert res.status_code == 404
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"


def test_process_limit_out_of_range(client):
    res = client.get("/api/processes?limit=100000")
    body = res.get_json()
    assert res.status_code == 400
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_PARAMETER"


def test_process_limit_non_integer(client):
    res = client.get("/api/processes?limit=abc")
    body = res.get_json()
    assert res.status_code == 400
    assert body["error"]["code"] == "INVALID_PARAMETER"


def test_process_limit_valid_range(client):
    data = _get(client, "/api/processes?limit=5")
    assert len(data["processes"]) <= 5


def test_invalid_process_filter(client):
    res = client.get("/api/processes?filter=bogus")
    body = res.get_json()
    assert res.status_code == 400
    assert body["error"]["code"] == "INVALID_PARAMETER"


def test_history_hours_out_of_range(client):
    res = client.get("/api/history?hours=9999")
    body = res.get_json()
    assert res.status_code == 400
    assert body["error"]["code"] == "INVALID_PARAMETER"


def test_history_limit_out_of_range(client):
    res = client.get("/api/history?limit=99999")
    body = res.get_json()
    assert res.status_code == 400
    assert body["error"]["code"] == "INVALID_PARAMETER"


def test_predictions_hours_out_of_range(client):
    res = client.get("/api/predictions?hours=0")
    body = res.get_json()
    assert res.status_code == 400
    assert body["error"]["code"] == "INVALID_PARAMETER"

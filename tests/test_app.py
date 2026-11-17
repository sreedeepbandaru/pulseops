"""Tests for PulseOps. Run:  python -m pytest tests/test_app.py -v
These use the Flask test client — no server, no AWS, no Docker needed.
"""
import os

os.environ["SIMULATE"] = "false"  # do not start the live simulator in tests

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import app as app_module


def client():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def test_home_page_loads():
    c = client()
    r = c.get("/")
    assert r.status_code == 200
    assert b"PulseOps" in r.data


def test_health_endpoint():
    c = client()
    r = c.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_api_health_endpoint():
    c = client()
    r = c.get("/api/health")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "ok"
    assert data["service"] == "pulseops"


def test_api_services_returns_eight_services():
    c = client()
    r = c.get("/api/services")
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list)
    assert len(data) == 8
    names = {s["name"] for s in data}
    assert "api-gateway" in names and "payments-api" in names


def test_api_incidents_returns_list():
    c = client()
    r = c.get("/api/incidents")
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "title" in data[0] and "severity" in data[0]


def test_api_metrics_has_expected_fields():
    c = client()
    r = c.get("/api/metrics")
    assert r.status_code == 200
    data = r.get_json()
    for field in ("cpu", "memory", "network_mbps", "requests_per_sec", "timestamp"):
        assert field in data


def test_api_logs_returns_list():
    c = client()
    r = c.get("/api/logs")
    assert r.status_code == 200
    assert isinstance(r.get_json()["logs"], list)


def test_prometheus_metrics_endpoint():
    c = client()
    r = c.get("/metrics")
    assert r.status_code == 200
    assert b"pulseops_cpu_percent" in r.data

"""PulseOps — Real-Time Operations Dashboard.

A small but realistic SRE dashboard. It shows live service health,
a live incident feed, a live log stream, and CPU / memory / network
charts that update every 2 seconds.

Run it locally (no AWS, no Docker needed):
    python -m venv .venv
    source .venv/bin/activate        # Windows: .venv\\Scripts\\activate
    pip install -r requirements.txt
    python app.py
Then open http://localhost:5000/

What it uses, in plain English:
- Flask: the web server.
- Flask-SocketIO: pushes live updates to the browser (WebSocket).
- SQLAlchemy: talks to the database (SQLite locally, Postgres on AWS).
- Redis: optional. If Redis is running, metrics are published there
  too. If it is not running, the app still works from memory.

Environment variables (all optional locally):
- DATABASE_URL: default sqlite:///pulseops.db (local file database)
- REDIS_URL: default redis://localhost:6379/0 — ignored if Redis is down
- SIMULATE: "true" by default. Set to "false" to stop the built-in
  simulator (the separate worker.py then supplies the live data).
- PORT: default 5000
"""

import json
import os
import random
import threading
import time
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
# SQLite locally, Postgres on AWS (DATABASE_URL is set by docker-compose
# and by Terraform/EC2). SQLite needs the check_same_thread flag off
# because the simulator thread also writes to the database.
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///pulseops.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "connect_args": {"check_same_thread": False}
} if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite") else {}

db = SQLAlchemy(app)
# threading mode: no extra server needed, works on Windows and Linux.
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Redis is optional. Never crash the app if Redis is not there.
redis_client = None
try:
    import redis

    redis_client = redis.Redis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        socket_connect_timeout=1,
        decode_responses=True,
    )
    redis_client.ping()
except Exception:
    redis_client = None


# ---------------------------------------------------------------------------
# Database models — the tables Postgres / SQLite will hold
# ---------------------------------------------------------------------------

class Service(db.Model):
    """One thing we watch, e.g. 'api-gateway' or 'payments-api'."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    status = db.Column(db.String(20), default="healthy")  # healthy/degraded/down
    uptime_pct = db.Column(db.Float, default=99.9)
    region = db.Column(db.String(40), default="us-east-1")
    cpu = db.Column(db.Float, default=0.0)
    memory = db.Column(db.Float, default=0.0)

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "status": self.status,
            "uptime_pct": self.uptime_pct, "region": self.region,
            "cpu": round(self.cpu, 1), "memory": round(self.memory, 1),
        }


class Incident(db.Model):
    """One problem, e.g. 'High error rate on checkout-api'."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    service = db.Column(db.String(80), nullable=False)
    severity = db.Column(db.String(20), default="warning")  # info/warning/critical
    status = db.Column(db.String(20), default="open")       # open/ack/resolved
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id, "title": self.title, "service": self.service,
            "severity": self.severity, "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Seed data — used only when the database is empty
# ---------------------------------------------------------------------------

SEED_SERVICES = [
    ("api-gateway", "us-east-1"), ("auth-service", "us-east-1"),
    ("payments-api", "us-east-1"), ("checkout-api", "us-east-1"),
    ("search-service", "us-east-1"), ("notifications", "us-east-1"),
    ("inventory-db", "us-east-1"), ("cdn-edge", "us-east-1"),
]

SEED_INCIDENTS = [
    ("High error rate on checkout-api", "checkout-api", "critical"),
    ("Elevated p99 latency on search-service", "search-service", "warning"),
    ("Payments API timeouts in us-east-1", "payments-api", "critical"),
    ("Auth token refresh failures", "auth-service", "warning"),
    ("Inventory DB replication lag", "inventory-db", "warning"),
    ("CDN cache hit ratio dropped", "cdn-edge", "info"),
    ("Notification queue backing up", "notifications", "warning"),
    ("API gateway 5xx spike", "api-gateway", "critical"),
]


def seed_if_empty():
    """Create tables and add starter services/incidents if there are none."""
    db.create_all()
    if Service.query.count() == 0:
        for name, region in SEED_SERVICES:
            db.session.add(Service(
                name=name, region=region,
                status=random.choice(["healthy", "healthy", "healthy", "degraded"]),
                uptime_pct=round(random.uniform(98.5, 99.99), 2),
                cpu=round(random.uniform(15, 65), 1),
                memory=round(random.uniform(25, 70), 1),
            ))
        for title, service, severity in SEED_INCIDENTS:
            db.session.add(Incident(title=title, service=service, severity=severity))
        db.session.commit()


with app.app_context():
    seed_if_empty()

# In-memory live state (charts + log stream). The worker also writes
# to the database; this keeps the dashboard live even without the worker.
LOG_LINES = [
    "2026-11-16 18:00:01 INFO  api-gateway request completed 200 in 42ms",
    "2026-11-16 18:00:02 INFO  payments-api charge succeeded order #88412",
    "2026-11-16 18:00:03 WARN  search-service p99 latency 812ms (threshold 500ms)",
    "2026-11-16 18:00:04 INFO  auth-service token refreshed for user 1042",
    "2026-11-16 18:00:05 INFO  inventory-db replica lag 1.2s",
]
LOG_MESSAGES = [
    ("INFO", "api-gateway", "request completed 200 in {n}ms"),
    ("INFO", "payments-api", "charge succeeded order #{n}"),
    ("WARN", "search-service", "p99 latency {n}ms (threshold 500ms)"),
    ("INFO", "auth-service", "token refreshed for user {n}"),
    ("INFO", "inventory-db", "replica lag {n}ms"),
    ("ERROR", "checkout-api", "timeout after 3000ms, retrying"),
    ("INFO", "cdn-edge", "cache hit ratio 94.2%"),
    ("INFO", "notifications", "email queued for user {n}"),
]

_latest_metrics = {"cpu": 32.0, "memory": 48.0, "network_mbps": 120.0, "requests_per_sec": 850}


def make_metrics():
    """Make one realistic sample of system metrics."""
    _latest_metrics["cpu"] = max(5, min(95, _latest_metrics["cpu"] + random.uniform(-6, 6)))
    _latest_metrics["memory"] = max(20, min(92, _latest_metrics["memory"] + random.uniform(-3, 3)))
    _latest_metrics["network_mbps"] = max(10, _latest_metrics["network_mbps"] + random.uniform(-25, 25))
    _latest_metrics["requests_per_sec"] = max(50, int(_latest_metrics["requests_per_sec"] + random.uniform(-80, 80)))
    return {
        **{k: round(v, 1) for k, v in _latest_metrics.items()},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def simulator_loop():
    """Background thread: every 2 seconds, push live data to all browsers."""
    while True:
        socketio.sleep(2)
        metrics = make_metrics()
        level, service, template = random.choice(LOG_MESSAGES)
        line = (
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} "
            f"{level} {service} {template.format(n=random.randint(20, 1200))}"
        )
        LOG_LINES.append(line)
        if len(LOG_LINES) > 100:
            LOG_LINES.pop(0)
        # Publish to Redis too, if it is available (worker/consumers listen).
        if redis_client is not None:
            try:
                redis_client.publish("pulseops:metrics", json.dumps(metrics))
            except Exception:
                pass
        with app.app_context():
            services = [s.to_dict() for s in Service.query.all()]
            incidents = [
                i.to_dict()
                for i in Incident.query.order_by(Incident.id.desc()).limit(10).all()
            ]
        socketio.emit("metrics", {
            "metrics": metrics,
            "services": services,
            "incidents": incidents,
            "log": line,
        })


if os.environ.get("SIMULATE", "true").lower() == "true":
    # Start only once, even when Flask reloads in debug mode.
    if not getattr(app, "_simulator_started", False):
        app._simulator_started = True
        socketio.start_background_task(simulator_loop)


# ---------------------------------------------------------------------------
# Pages and API
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    """Simple health check. Load balancers and the deploy step use this."""
    return jsonify(status="ok"), 200


@app.route("/api/health")
def api_health():
    return jsonify(status="ok", service="pulseops", version="1.0.0"), 200


@app.route("/api/services")
def api_services():
    return jsonify([s.to_dict() for s in Service.query.all()])


@app.route("/api/incidents")
def api_incidents():
    return jsonify([
        i.to_dict()
        for i in Incident.query.order_by(Incident.id.desc()).limit(25).all()
    ])


@app.route("/api/metrics")
def api_metrics():
    return jsonify(make_metrics())


@app.route("/api/logs")
def api_logs():
    return jsonify({"logs": LOG_LINES[-50:]})


@app.route("/metrics")
def prometheus_metrics():
    """Very small Prometheus-style endpoint (text format)."""
    m = _latest_metrics
    body = (
        "# HELP pulseops_cpu_percent Current CPU percent\n"
        "# TYPE pulseops_cpu_percent gauge\n"
        f"pulseops_cpu_percent {m['cpu']}\n"
        "# HELP pulseops_memory_percent Current memory percent\n"
        "# TYPE pulseops_memory_percent gauge\n"
        f"pulseops_memory_percent {m['memory']}\n"
        "# HELP pulseops_requests_per_second Requests per second\n"
        "# TYPE pulseops_requests_per_second gauge\n"
        f"pulseops_requests_per_sec {m['requests_per_sec']}\n"
    )
    return body, 200, {"Content-Type": "text/plain; version=0.0.4"}


@socketio.on("connect")
def on_connect():
    """When a browser opens the dashboard, send it the current state."""
    with app.app_context():
        services = [s.to_dict() for s in Service.query.all()]
        incidents = [
            i.to_dict()
            for i in Incident.query.order_by(Incident.id.desc()).limit(10).all()
        ]
    socketio.emit("metrics", {
        "metrics": make_metrics(), "services": services,
        "incidents": incidents, "log": LOG_LINES[-1] if LOG_LINES else "",
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    print(f"PulseOps running at http://localhost:{port}/")
    # allow_unsafe_werkzeug=True is only for local development.
    # In Docker / on AWS the app runs under gunicorn (see Dockerfile).
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)

"""PulseOps worker — the background simulator.

Runs separately from the web app (its own container on AWS, its own
process locally). Every 2 seconds it:
  1. Makes realistic metrics (CPU, memory, network, requests/sec).
  2. Updates service health in the database.
  3. Sometimes creates a new incident or log line.
  4. Publishes the metrics to Redis (channel pulseops:metrics).

Run locally:
    python worker.py
It needs the same DATABASE_URL / REDIS_URL as app.py. If Postgres or
Redis are not running, it prints a warning and keeps simulating in
memory — it never crashes the dashboard.
"""

import json
import os
import random
import time
from datetime import datetime, timezone

# Reuse the models and seed data from app.py so worker and web agree.
import sys
sys.path.insert(0, os.path.dirname(__file__))

from app import app, db, Service, Incident, make_metrics, LOG_MESSAGES

redis_client = None
try:
    import redis

    redis_client = redis.Redis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        socket_connect_timeout=1, decode_responses=True,
    )
    redis_client.ping()
    print("Worker: connected to Redis")
except Exception as exc:
    print(f"Worker: Redis not available ({exc}) — continuing without it")

INCIDENT_TITLES = [
    ("High error rate on {s}", "critical"),
    ("Elevated p99 latency on {s}", "warning"),
    ("{s} timeouts in us-east-1", "critical"),
    ("{s} queue backing up", "warning"),
    ("{s} cache hit ratio dropped", "info"),
]


def main():
    print("PulseOps worker started — generating metrics every 2s")
    tick = 0
    while True:
        tick += 1
        metrics = make_metrics()
        if redis_client is not None:
            try:
                redis_client.publish("pulseops:metrics", json.dumps(metrics))
            except Exception:
                pass
        # Update the database every tick (cheap, small tables).
        try:
            with app.app_context():
                services = Service.query.all()
                for svc in services:
                    svc.cpu = max(5, min(95, svc.cpu + random.uniform(-8, 8)))
                    svc.memory = max(20, min(92, svc.memory + random.uniform(-4, 4)))
                    if random.random() < 0.02:
                        svc.status = random.choice(["healthy", "degraded"])
                # About once a minute, open a new incident.
                if tick % 30 == 0:
                    svc = random.choice(services)
                    title, severity = random.choice(INCIDENT_TITLES)
                    db.session.add(Incident(
                        title=title.format(s=svc.name),
                        service=svc.name, severity=severity,
                    ))
                    print(f"Worker: new incident on {svc.name} ({severity})")
                db.session.commit()
        except Exception as exc:
            print(f"Worker: database write skipped ({exc})")
        print(
            f"{datetime.now(timezone.utc).strftime('%H:%M:%S')} "
            f"cpu={metrics['cpu']}% mem={metrics['memory']}% "
            f"rps={metrics['requests_per_sec']}"
        )
        time.sleep(2)


if __name__ == "__main__":
    main()

"""Seed PulseOps with realistic data: 8 services, 25 incidents.

Run:  python seed.py
It wipes the Service and Incident tables first, then re-creates them.
Safe to run again any time. Uses the same DATABASE_URL as app.py
(SQLite locally, Postgres on AWS).
"""

import random
from datetime import datetime, timedelta, timezone

from app import app, db, Service, Incident

SERVICES = [
    # (name, region, uptime)
    ("api-gateway", "us-east-1", 99.99),
    ("auth-service", "us-east-1", 99.95),
    ("payments-api", "us-east-1", 99.92),
    ("checkout-api", "us-east-1", 99.87),
    ("search-service", "us-east-1", 99.94),
    ("notifications", "us-east-1", 99.98),
    ("inventory-db", "us-east-1", 99.99),
    ("cdn-edge", "us-east-1", 99.99),
]

INCIDENT_TEMPLATES = [
    ("High error rate on {s}", "critical"),
    ("Elevated p99 latency on {s}", "warning"),
    ("{s} timeouts in us-east-1", "critical"),
    ("{s} queue backing up", "warning"),
    ("{s} cache hit ratio dropped", "info"),
    ("{s} deployment rolled back", "warning"),
    ("{s} disk usage above 80%", "warning"),
    ("{s} SSL certificate expiring in 14 days", "info"),
    ("{s} pod restarted unexpectedly", "warning"),
    ("{s} upstream dependency slow", "critical"),
]

with app.app_context():
    db.create_all()
    Incident.query.delete()
    Service.query.delete()
    for name, region, uptime in SERVICES:
        db.session.add(Service(
            name=name, region=region, uptime_pct=uptime,
            status=random.choice(["healthy", "healthy", "healthy", "degraded"]),
            cpu=round(random.uniform(15, 65), 1),
            memory=round(random.uniform(25, 70), 1),
        ))
    now = datetime.now(timezone.utc)
    for i in range(25):
        service = random.choice([s[0] for s in SERVICES])
        title, severity = random.choice(INCIDENT_TEMPLATES)
        db.session.add(Incident(
            title=title.format(s=service), service=service,
            severity=severity,
            status=random.choice(["open", "open", "ack", "resolved"]),
            created_at=now - timedelta(minutes=random.randint(5, 4000)),
        ))
    db.session.commit()
    print(f"Seeded {Service.query.count()} services, "
          f"{Incident.query.count()} incidents.")

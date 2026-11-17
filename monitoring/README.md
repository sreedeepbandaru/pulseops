# Monitoring — PulseOps

## What is watched
1. **`/health`** — the simplest check. Docker, the pipeline, and the load
   balancer all call it. If it stops answering 200, something is wrong.
2. **`/metrics`** — a small Prometheus endpoint: CPU %, memory %, requests/sec.
3. **Logs** — `docker compose logs -f web` on the server, or CloudWatch
   log group `/pulseops/app` on AWS.

## Locally (with Docker Compose, monitoring profile)
```bash
docker compose --profile monitoring up --build
```
- Prometheus: http://localhost:9090 — try the query `pulseops_cpu_percent`
- Grafana: http://localhost:3000 — log in as `admin` / `admin`, then
  Add data source → Prometheus → URL `http://prometheus:9090` → Save.
  Then create a dashboard, add a panel, and use the query
  `pulseops_cpu_percent` (or `pulseops_memory_percent`,
  `pulseops_requests_per_sec`).

## On AWS (EC2)
The same Prometheus/Grafana containers can run on the EC2 server, but
they are not in the default deploy — the server is a small t3.small.
If you want them there, add the `prometheus` and `grafana` services
from docker-compose.yml to the server's compose file, open ports
9090 and 3000 in the Terraform security group, and change the Grafana
admin password immediately. For a first project, checking `/health`
and `docker compose logs -f` is enough.

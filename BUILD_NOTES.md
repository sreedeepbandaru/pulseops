# Build notes — PulseOps

Built 2026-11-16/17 for Sreedeep. Replaces the tiny Flask demo; none of
that demo's app code was reused.

## What was verified locally (in this VM)
- **Tests: 8 passed, 0 failed** — `python -m pytest tests/test_app.py -v`
  (run twice, including once after the final fix). Tests cover `/`,
  `/health`, `/api/health`, `/api/services` (exactly 8 services),
  `/api/incidents`, `/api/metrics` fields, `/api/logs`, `/metrics`.
- **App actually started and responded** — ran `python app.py` in the
  background (SIMULATE=false) and curled it:
  - `GET /` → 200, PulseOps dashboard HTML
  - `GET /health` → 200 `{"status":"ok"}`
  - `GET /api/health` → 200 `{"service":"pulseops","status":"ok","version":"1.0.0"}`
  - `GET /api/services` → 200, 8 services (api-gateway, auth-service,
    payments-api, checkout-api, search-service, notifications,
    inventory-db, cdn-edge)
  - `GET /api/metrics` → 200, e.g. cpu 37.7, memory 48.0,
    network_mbps 119.6, requests_per_sec 870
  - `GET /api/incidents` → 200, 8 seeded incidents
  - `GET /metrics` → 200, Prometheus text with pulseops_cpu_percent etc.
- **Seed script verified** — `python seed.py` printed
  "Seeded 8 services, 25 incidents." and a direct DB check confirmed
  8 services / 25 incidents.
- **Syntax checks** — `python -m py_compile` passed for app.py,
  worker.py, seed.py, test_app.py. YAML files checked for tabs;
  no real secrets found by grep (one README line only mentions the
  `.pem` header as guidance for copying a key into GitHub Secrets).
- **One bug found and fixed during verification:** the first run
  crashed with `RuntimeError: The Werkzeug web server is not designed
  to run in production.` Fixed by adding `allow_unsafe_werkzeug=True`
  to `socketio.run()` in app.py (local dev only; Docker/AWS use
  gunicorn). Re-verified after the fix; tests re-passed 8/8.

## What was NOT verified
- **Docker build** — Docker is not installed in this VM, so neither
  Dockerfile was built and `docker compose up` was never run.
- **Terraform** — Terraform is not installed in this VM, so
  `terraform fmt` / `terraform validate` were NOT run. HCL was
  written carefully and eye-checked only. No `terraform apply` was
  run and no AWS calls were made, as instructed.
- **GitHub Actions** — the pipeline was never run (no GitHub account/repo).
- **AWS deploy** — nothing was deployed to AWS; no AWS account exists yet.
- **Socket.IO live push in a real browser** — endpoints and the
  simulator thread were verified via curl/tests, but the 2-second
  chart animation was not watched in a browser here.

## Files created (all new, in ~/workspace/aws-realtime-app)
- README.md, BUILD_NOTES.md, .env.example, .gitignore
- Dockerfile, Dockerfile.worker, docker-compose.yml, nginx.conf
- app/app.py, app/worker.py, app/seed.py, app/requirements.txt
- app/templates/index.html, app/static/css/style.css, app/static/js/dashboard.js
- tests/test_app.py
- .github/workflows/ci-cd.yml
- terraform/main.tf, terraform/variables.tf, terraform/outputs.tf,
  terraform/terraform.tfvars.example, terraform/README.md
- monitoring/prometheus.yml, monitoring/README.md

No secrets are in any file. No `.env`, no `.venv`, no database file,
no `__pycache__` was left in the project.

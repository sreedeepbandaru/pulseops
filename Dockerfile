# PulseOps web app — Dockerfile
# Build:  docker build -t pulseops-web:1.0 .
# Run:    docker run -p 5000:5000 pulseops-web:1.0
FROM python:3.12-slim
WORKDIR /app
# Install libraries first (Docker caches this step when only code changes).
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ .
EXPOSE 5000
# gunicorn + eventlet worker so Socket.IO works in production.
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--bind", "0.0.0.0:5000", "app:app"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')"

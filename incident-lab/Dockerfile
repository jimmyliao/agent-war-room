# incident-lab as a Cloud Run service.
#
# Zero-dependency Python 3 HTTP service. Cloud Run injects PORT and expects the
# container to bind 0.0.0.0:$PORT. server.py already accepts --host/--port, so
# we only translate the Cloud Run contract into those flags at startup.
#
# TRUST BOUNDARY: we deliberately COPY only server.py and fault_store.py. The
# incidents/ and scenarios/ directories hold evaluator ground truth and must
# never land in an agent-facing runtime. .dockerignore also excludes them as a
# second guard. The service itself never reads incidents/ (see README).

FROM python:3.11-slim

WORKDIR /app

# Only the runnable service. No ground-truth, no scenarios, no logs/state.
COPY server.py fault_store.py ./

# Writable dirs for volatile fault state + logs (ephemeral on Cloud Run).
RUN mkdir -p /app/state /app/logs

ENV PYTHONUNBUFFERED=1

# Cloud Run sets $PORT (default 8080). Bind 0.0.0.0 for external ingress.
# Shell form is required so $PORT expands at runtime.
CMD exec python3 server.py --host 0.0.0.0 --port "${PORT:-8080}"

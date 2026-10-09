# ================================================================================
# Thoughts Dashboard — Containerfile
# Runtime: registry.access.redhat.com/hi/python:latest (Hummingbird hardened,
#          non-root UID 65532, no package manager — distroless-style)
# Builder: registry.access.redhat.com/ubi9/python-311:latest (has dnf to compile
#          native extensions; discarded after build — never ships in final image)
# Spec: specs/deployment/dockerfile.spec
#
# CRITICAL: ONLY Red Hat images approved (registry.access.redhat.com)
#           Do NOT use python:3.11, python:3.11-slim, or any docker.io images
# ================================================================================

# ── Stage 1: Builder (UBI9 python-311 — has dnf, gcc, postgresql-devel) ───────
# The builder is never shipped. It exists only to compile native extensions and
# install all Python packages into /opt/venv, which is then copied to runtime.
FROM registry.access.redhat.com/ubi9/python-311:latest AS builder

# Switch to root to install system packages (UBI images default to non-root UID 1001)
USER root

# Install build dependencies — these are NOT in the final image
RUN dnf install -y \
        gcc \
        postgresql-devel \
        python3-devel \
    && dnf clean all \
    && rm -rf /var/cache/dnf

# Create virtual environment at /opt/venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements first to leverage layer caching — only rebuilt when deps change
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Runtime (Hardened Image — no package manager, UID 65532) ─────────
FROM registry.access.redhat.com/hi/python:latest

# Python runtime settings — NO secrets (injected at runtime via Kubernetes Secrets)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8080

# Copy only the pre-built venv — compiler and build tools stay in the builder
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Hardened image runs as UID 65532; group 0 required for OpenShift compatibility
COPY --chown=65532:0 src/    /app/src/
COPY --chown=65532:0 config/ /app/config/

# Explicitly set non-root user (best practice for clarity — image default is 65532)
USER 65532

EXPOSE 8080

# Health check — uses Python stdlib only (no curl/wget in distroless-style image)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c \
        "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" \
        || exit 1

# Production WSGI server — flask dev server is forbidden (spec REQ-7)
# Logging to stdout/stderr for container log aggregation (12-factor app)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "4", \
     "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-", \
     "src.app:app"]

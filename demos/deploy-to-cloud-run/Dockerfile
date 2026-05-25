# syntax=docker/dockerfile:1.7

# Single source of truth for the Python version. Bump here and both stages
# below pick it up. Pin the patch + distro: `3.12-slim` silently rolls forward
# on every base-image push, which is exactly what supply-chain scanners hate.
ARG PYTHON_VERSION=3.12.7

# ============================================================================
# Stage 1 — builder
#
# Installs all Python dependencies into an isolated virtualenv at /opt/venv.
# The runtime stage will copy the venv as a single self-contained directory,
# leaving pip, the build cache, and requirements.txt behind.
# ============================================================================
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /build
COPY requirements.txt .
RUN pip install -r requirements.txt

# ============================================================================
# Stage 2 — runtime
#
# Minimal image: just the venv from the builder, the app source, and a
# non-root user to run as.
# ============================================================================
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

LABEL org.opencontainers.image.title="GCP Bootcamp Masterclass API" \
      org.opencontainers.image.description="FastAPI progressive-canary demo on Cloud Run" \
      org.opencontainers.image.source="https://github.com/ArnauSB/gcp-examples"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    PATH="/opt/venv/bin:${PATH}"

# Create an unprivileged user. UID/GID 10001 is comfortably above the system
# range, conventional for "definitely-not-root" service accounts. Running as
# root inside a container is a frequent CVE multiplier; drop the privilege.
RUN groupadd --gid 10001 app \
 && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app

# Copy the prebuilt venv. No pip, no requirements.txt, no build cache makes
# it into the runtime image — this is the whole point of the split.
COPY --from=builder --chown=app:app /opt/venv /opt/venv

WORKDIR /code
COPY --chown=app:app ./app /code/app

USER app
EXPOSE 8080

# `exec` replaces the shell with uvicorn so SIGTERM from Cloud Run reaches
# uvicorn directly. Without it, the shell swallows the signal and Cloud Run
# waits the full grace period (10s) before SIGKILL on every revision swap.
# The `sh -c` wrapper is here so ${PORT} expands at container start (Cloud
# Run sets it dynamically per service config).
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]

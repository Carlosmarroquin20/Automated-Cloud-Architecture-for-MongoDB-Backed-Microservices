# syntax=docker/dockerfile:1

# ------------------------------------------------------------------------------
# Builder stage
# Dependencies are resolved into an isolated target directory so the runtime
# image carries only the installed packages and none of the build tooling. The
# interpreter minor version matches the distroless runtime (Python 3.11) so the
# prebuilt wheels are binary-compatible.
# ------------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY requirements.txt .
RUN pip install --target=/deps -r requirements.txt

# ------------------------------------------------------------------------------
# Runtime stage
# Distroless carries no shell, package manager, or extraneous binaries, which
# minimizes the attack surface, and defaults to an unprivileged user.
# ------------------------------------------------------------------------------
FROM gcr.io/distroless/python3-debian12 AS runtime

WORKDIR /app
COPY --from=builder /deps /deps
COPY app ./app

# Third-party packages and the application source are both placed on the import
# path; bytecode writing is disabled since the filesystem is treated as immutable.
ENV PYTHONPATH=/app:/deps \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Runs as the distroless non-root user (uid 65532).
USER nonroot

# Binding to all interfaces is required for container ingress; external exposure
# is governed by the orchestrator, not the process.
ENTRYPOINT ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

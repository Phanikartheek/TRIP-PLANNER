# Multi-stage production Dockerfile for AI Trip Planner
FROM python:3.11-slim as builder

WORKDIR /app

# Install curl for container health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python package dependencies first for layer caching
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Copy application source code
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY run.py ./

# Re-install package in editable mode with copied source
RUN pip install --no-cache-dir -e .

# Expose HTTP port
EXPOSE 8000

# Environment defaults
ENV PORT=8000 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend/src

# Healthcheck to verify FastAPI is responding
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

# Launch the server
CMD ["python", "run.py"]

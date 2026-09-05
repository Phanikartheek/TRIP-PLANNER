FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy ALL source FIRST (backend/src must exist before pip install -e .)
COPY pyproject.toml ./
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY run.py ./

# Now install — backend/src exists so editable install works correctly
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Expose default port (Railway overrides via $PORT env var)
EXPOSE 8000

# Environment defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend/src

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8000}/api/health || exit 1

# Shell form so $PORT env var is expanded by Railway at runtime
CMD uvicorn trip_planner.api.app:app --app-dir backend/src --host 0.0.0.0 --port ${PORT:-8000}

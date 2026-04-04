# ── Stage 1: base ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

# Prevents Python from writing .pyc files and buffers stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ── Stage 2: dependencies ──────────────────────────────────────────────────────
FROM base AS deps

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 3: final image ───────────────────────────────────────────────────────
FROM deps AS final

# Create non-root user for security
RUN addgroup --system aiops && adduser --system --ingroup aiops aiops

# Copy application code
COPY --chown=aiops:aiops . .

# Ensure storage and log directories exist and are writable
RUN mkdir -p storage logs && chown -R aiops:aiops storage logs

USER aiops

EXPOSE 8000

# Health check — Kubernetes liveness probe compatible
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Default: run the FastAPI server
# Override CMD to run the Streamlit dashboard:
#   docker run -p 8501:8501 aiops-platform streamlit run dashboard/streamlit_app.py --server.port 8501
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

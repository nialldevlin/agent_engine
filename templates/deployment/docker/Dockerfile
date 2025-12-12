# Multi-stage Dockerfile for Agent Engine deployment
# Recommended for production containerized deployments

# Stage 1: Builder
FROM python:3.10-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml requirements.txt* README.md LICENSE ./

# Build wheel
RUN pip install build && \
    python -m build --wheel

# Copy source code
COPY src ./src
COPY tests ./tests

# Rebuild with source
RUN rm -rf dist/ && \
    python -m build --wheel

# Stage 2: Runtime
FROM python:3.10-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 agentuser

# Copy built wheel from builder
COPY --from=builder /build/dist/*.whl /tmp/

# Install agent-engine wheel
RUN pip install --no-cache-dir /tmp/*.whl && \
    rm /tmp/*.whl

# Copy configuration directory
COPY config ./config

# Copy scripts
COPY scripts ./scripts
RUN chmod +x scripts/*.sh scripts/*.py

# Copy .env.template (not .env!)
COPY .env.template .env.template

# Create data and logs directories
RUN mkdir -p data logs artifacts && \
    chown -R agentuser:agentuser /app

# Switch to non-root user
USER agentuser

# Set Python to run in unbuffered mode
ENV PYTHONUNBUFFERED=1

# Set configuration directory
ENV AGENT_ENGINE_CONFIG_DIR=/app/config

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python /app/scripts/healthcheck.py || exit 1

# Default command: run health check
CMD ["python", "/app/scripts/healthcheck.py"]

# Labels for metadata
LABEL org.opencontainers.image.title="Agent Engine" \
      org.opencontainers.image.description="Multi-agent LLM orchestration engine" \
      org.opencontainers.image.version="0.0.1" \
      org.opencontainers.image.vendor="Agent Engine Team"

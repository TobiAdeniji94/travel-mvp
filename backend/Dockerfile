# syntax=docker/dockerfile:1.4

# Multi-stage build for optimized production image
FROM python:3.13-slim as base

# Install system dependencies and security updates
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    curl \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Set up application directory
WORKDIR /app
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install Python dependencies in split, cache-friendly layers
COPY requirements/ ./requirements/
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel \
    && pip install -r requirements/base.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements/app.txt

# Verify spaCy model is importable (no extra downloads here)
RUN python -c "import spacy; spacy.load('en_core_web_lg')"

# Copy and set up startup script
COPY start.sh .
RUN chmod +x start.sh \
    && chown appuser:appuser start.sh

# Copy application code
COPY --chown=appuser:appuser . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/logs /app/models /app/temp \
    && chown -R appuser:appuser /app/logs /app/models /app/temp

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Set default environment variables
ENV FASTAPI_ENV=production
ENV LOG_LEVEL=info

# Use exec form for better signal handling
ENTRYPOINT ["./start.sh"]

# Add labels for better container management
LABEL maintainer="Travel MVP Team" \
      version="1.0" \
      description="Travel MVP Backend API with enhanced NLP and ML capabilities" \
      org.opencontainers.image.source="https://github.com/TobiAdeniji94/travel-mvp"

# Production stage to match compose.prod target
FROM base as production
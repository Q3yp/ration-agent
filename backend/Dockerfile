# Backend Dockerfile for Ration Agent
# Single-stage build for production image

FROM python:3.13-slim

# Install system dependencies for building and runtime
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

ENV UV_PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/

# Install uv to system-wide location (accessible by all users)
RUN curl -LsSf https://astral.sh/uv/install.sh | env CARGO_HOME=/usr/local UV_INSTALL_DIR=/usr/local/bin sh

# Create non-root user for security and home directory
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN mkdir -p /home/appuser && chown -R appuser:appuser /home/appuser

# Set working directory and ownership
WORKDIR /app
RUN chown appuser:appuser /app

# Switch to non-root user
USER appuser
ENV HOME="/home/appuser"

# Copy pyproject.toml and uv.lock first for better layer caching
COPY --chown=appuser:appuser pyproject.toml uv.lock ./

# Copy nasem_dairy package (local dependency)
COPY --chown=appuser:appuser nasem_dairy/ ./nasem_dairy/

# Install dependencies and build nasem_dairy during Docker build (not at runtime)
# Use --frozen to ensure uv doesn't try to update lockfile
RUN uv sync --frozen --index-url https://mirrors.aliyun.com/pypi/simple/

# Copy remaining source code
COPY --chown=appuser:appuser . .

# Ensure files directory exists
RUN mkdir -p /app/files

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=10)" || exit 1

# Start the application using the pre-built virtual environment
ENTRYPOINT ["uv", "run", "--frozen", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
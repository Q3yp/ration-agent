# Backend Dockerfile for Ration Agent
# Single-stage build for production image

FROM docker.1ms.run/python:3.11-slim

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

# Copy all source code (including nasem_dairy local package)
COPY --chown=appuser:appuser . .

# Install dependencies using uv (nasem_dairy is a local editable dependency)
RUN uv sync --index-url https://mirrors.aliyun.com/pypi/simple/

# Ensure files directory exists
RUN mkdir -p /app/files

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=10)" || exit 1

# Start the application
ENTRYPOINT ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
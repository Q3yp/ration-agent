# Backend Dockerfile for Ration Agent
# Single-stage build for production image

FROM docker.1ms.run/python:3.11-slim

# Install system dependencies for building and runtime
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

ENV UV_PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# Install uv for fast Python package management
RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv (no dev for lean runtime) and force system Python
RUN uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# Copy application code
COPY . .

# Add virtual environment to PATH and configure Python
# ENV PATH="/app/.venv/bin:$PATH"
# ENV PYTHONDONTWRITEBYTECODE=1
# ENV PYTHONUNBUFFERED=1
ENV HOME="/home/appuser"

# Create non-root user for security and set permissions
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN mkdir -p /home/appuser && chown -R appuser:appuser /home/appuser
RUN mkdir -p /app/files && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=10)" || exit 1

# Start the application (avoid uv runtime cache permissions)
ENTRYPOINT ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

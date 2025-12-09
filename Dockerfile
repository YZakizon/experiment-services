# Use official Python image
FROM python:3.13-slim

# Set working directory
WORKDIR /app
RUN mkdir /app/log

# Install curl
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Install dependencies
# COPY requirements.txt ./
# RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml uv.lock ./
# Install dependencies into a local directory (no venv)
RUN uv sync --locked

# Add Docker healthcheck using curl
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl --fail http://localhost:9000/health || exit 1

# Copy application code
COPY . .

# Expose port
EXPOSE 9000

# Run using gunicorn + uvicorn workers
CMD ["uv", "run", "gunicorn", "main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:9000"]
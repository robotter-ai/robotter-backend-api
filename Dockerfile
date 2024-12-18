# Build stage
FROM python:3.10-slim as builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install poetry

# Copy only dependency files
WORKDIR /app
COPY pyproject.toml poetry.lock* ./

# Configure poetry to not create a virtual environment (we're in a container)
RUN poetry config virtualenvs.create false

# Install dependencies
RUN poetry install --no-dev --no-interaction --no-ansi

# Runtime stage
FROM python:3.10-slim

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

WORKDIR /app

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

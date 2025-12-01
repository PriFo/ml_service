# Multi-stage build for ML Service v3.2

# Backend stage
FROM python:3.10-slim as backend

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ml_service_new ./ml_service_new

# Set environment variables
ENV PYTHONPATH=/app
ENV ML_SERVICE_HOST=0.0.0.0
ENV ML_SERVICE_PORT=8085

# Expose port
EXPOSE 8085

# Run backend
CMD ["python", "-m", "ml_service_new"]


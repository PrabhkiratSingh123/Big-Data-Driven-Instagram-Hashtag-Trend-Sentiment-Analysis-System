FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared storage module
COPY --from=storage ../storage /app/storage

# Copy application code
COPY . .

# Set Python path so imports work
ENV PYTHONPATH=/app:/app/..
ENV PYTHONUNBUFFERED=1

CMD ["python", "kafka_producer.py"]

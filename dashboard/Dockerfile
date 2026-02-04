FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/aydinguven/vm-monitor"
LABEL org.opencontainers.image.description="VM Monitor Dashboard - Self-hosted VM monitoring system"

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application code
COPY . .

# Create instance directory for runtime config
RUN mkdir -p instance

# Non-root user for security
RUN useradd -r -s /bin/false vmmonitor && \
    chown -R vmmonitor:vmmonitor /app
USER vmmonitor

EXPOSE 5000

# Use Gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "app:app"]

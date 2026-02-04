FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/aydinguven/vm-monitor"
LABEL org.opencontainers.image.description="VM Monitor Agent - Lightweight monitoring agent"

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent
COPY agent.py .

# Create config directory
RUN mkdir -p /etc/vm-agent

# Agent runs as root to collect system metrics (required for psutil)
# Config can be mounted at /etc/vm-agent/agent_config.json

ENTRYPOINT ["python", "-u", "agent.py"]

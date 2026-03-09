# Configuration Guide

This guide covers all configuration options for the VM Monitor system.

## Dashboard Configuration

### Environment Variables

Set these in your systemd service file or `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `VM_DASHBOARD_API_KEY` | `changeme` | API key for agent authentication |
| `FLASK_SECRET_KEY` | random | Flask session secret (set for production) |
| `DATABASE_URL` | `sqlite:///vm_metrics.db` | Database connection |
| `METRIC_RETENTION_HOURS` | `24` | Metric history retention |
| `CLEANUP_INTERVAL_MINUTES` | `60` | Cleanup job interval |
| `VM_OFFLINE_THRESHOLD` | `120` | Seconds before VM marked offline |
| `ALERT_WARNING_THRESHOLD` | `80` | Warning threshold (%) |
| `ALERT_CRITICAL_THRESHOLD` | `90` | Critical threshold (%) |

### Config Files

Config files are stored in `instance/` directory:

#### `instance/sms_config.json`

```json
{
  "provider": "twilio",
  "recipient": "+1234567890",
  "dashboard_url": "https://your-dashboard.com",
  "twilio": {
    "account_sid": "ACxxxxxxxxx",
    "auth_token": "your-token",
    "from_number": "+1987654321"
  }
}
```

#### `instance/features.json`

```json
{
  "commands": true,
  "sms": true,
  "alerts": true,
  "containers": true,
  "pods": true,
  "auto_update": true,
  "gpu": true
}
```

## Agent Configuration

### Environment Variables

Set in `agent_config.json` at `/opt/vm-agent/` (Linux) or `C:\vm-agent\` (Windows):

```json
{
  "server_url": "https://your-dashboard.com",
  "api_key": "your_api_key",
  "interval": 30,
  "hostname": "custom-hostname",
  "auto_update": true,
  "features": {
    "containers": true,
    "pods": true,
    "commands": true,
    "gpu": true
  }
}
```

Legacy agents will also read `VM_AGENT_SERVER`, `VM_AGENT_KEY`, `VM_AGENT_INTERVAL`, and `VM_AGENT_GPU` environment variables.

### Agent Installation Options

**Linux:**
```bash
./setup.sh --batch --server https://dashboard.com --key YOUR_API_KEY --interval 30 --gpu
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1 -Batch -Server "https://dashboard.com" -Key "YOUR_API_KEY" -Gpu
```

## Production Deployment

### Systemd Service (Dashboard)

```ini
[Unit]
Description=VM Monitor Dashboard
After=network.target

[Service]
Type=simple
User=vm-dashboard
WorkingDirectory=/opt/vm-dashboard
Environment=VM_DASHBOARD_API_KEY=your-secure-key
Environment=FLASK_SECRET_KEY=your-secret-key
ExecStart=/opt/vm-dashboard/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

### Nginx Reverse Proxy

```nginx
server {
    listen 443 ssl;
    server_name monitor.example.com;
    
    ssl_certificate /etc/letsencrypt/live/monitor.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/monitor.example.com/privkey.pem;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Security Recommendations

1. **Use HTTPS** - Always use TLS in production
2. **Strong API Key** - Generate a secure random key
3. **Firewall** - Restrict dashboard access to trusted IPs
4. **File Permissions** - Protect config files containing secrets
   ```bash
   chmod 600 instance/sms_config.json
   ```

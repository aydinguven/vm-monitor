# VM Monitor

A lightweight, self-hosted VM monitoring system with a Python agent and Flask-based web dashboard.

![Dashboard Screenshot](docs/dashboard-preview.png)

## Features

- **Real-time Monitoring** - CPU, RAM, Disk usage with historical charts
- **Multi-Platform** - Linux (RHEL/CentOS/Ubuntu) and Windows support
- **Container Discovery** - Docker, Podman (rootless included), Kubernetes pods
- **SMS Alerts** - Twilio, Textbelt, İleti Merkezi integration
- **Remote Commands** - Execute commands on agents from dashboard
- **Auto-Updates** - Agents automatically update from your server
- **Cloud Detection** - AWS, GCP, Azure, Oracle Cloud, Proxmox, VMware

## Quick Start

### 1. Deploy Dashboard

```bash
# Clone the repository
git clone https://github.com/your-username/vm-monitor.git
cd vm-monitor/dashboard

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run dashboard
flask run --host=0.0.0.0 --port=5000
```

For production, use gunicorn:
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### 2. Install Agent (Linux)

```bash
curl -sL https://your-server/install_agent.sh | sudo bash -s -- \
  --server https://your-dashboard:5000 \
  --key YOUR_API_KEY
```

### 3. Install Agent (Windows)

```powershell
# Run PowerShell as Administrator
.\install_agent.ps1 -Server "https://your-dashboard:5000" -Key "YOUR_API_KEY"
```

## Configuration

### Dashboard Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VM_DASHBOARD_API_KEY` | `changeme` | API key for agent authentication |
| `FLASK_SECRET_KEY` | (random) | Flask session secret |
| `DATABASE_URL` | `sqlite:///vm_metrics.db` | Database connection string |
| `METRIC_RETENTION_HOURS` | `24` | How long to keep metric history |

### Agent Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VM_AGENT_SERVER` | (required) | Dashboard URL |
| `VM_AGENT_KEY` | `changeme` | API key matching dashboard |
| `VM_AGENT_INTERVAL` | `15` | Push interval in seconds |
| `VM_AGENT_HOSTNAME` | (auto) | Override hostname |

### SMS Alerts

Configure via `instance/sms_config.json`:

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

Supported providers: `twilio`, `textbelt`, `iletimerkezi`, `disabled`

### Feature Flags

Enable/disable features via `instance/features.json`:

```json
{
  "commands": true,
  "sms": true,
  "alerts": true,
  "containers": true,
  "pods": true,
  "auto_update": true
}
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/metrics` | POST | Agent metric submission |
| `/api/vms` | GET | List all VMs |
| `/api/vm/<hostname>/history` | GET | VM metric history |
| `/api/send-sms` | POST | Manual SMS trigger |
| `/api/schedule` | GET | View SMS schedule |
| `/api/features` | GET/POST | Manage feature flags |
| `/api/sms-config` | GET/POST | Manage SMS config |

## Directory Structure

```
vm-monitor/
├── agent/              # Monitoring agent
│   ├── agent.py
│   ├── requirements.txt
│   └── install_agent.ps1
├── dashboard/          # Web dashboard
│   ├── app.py
│   ├── config.py
│   ├── models.py
│   ├── templates/
│   └── static/
├── scripts/            # Installation scripts
│   ├── install_agent.sh
│   ├── install_dashboard.sh
│   └── cleanup.sh
└── docs/               # Documentation
```

## Security Notes

- Always use HTTPS in production
- Change the default API key
- Restrict dashboard access with firewall rules
- SMS config file contains secrets - set proper permissions

## License

MIT License - See [LICENSE](LICENSE) file

## Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

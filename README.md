# VM Monitor


A lightweight, self-hosted VM monitoring system with a Python agent and Flask-based web dashboard.

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
git clone https://github.com/aydinguven/vm-monitor.git
cd vm-monitor

# Interactive setup (recommended)
./scripts/setup_dashboard.sh

# Or batch mode
./scripts/setup_dashboard.sh --batch --api-key YOUR_KEY
```

### 2. Install Agent (Linux)

```bash
# Interactive setup
./scripts/setup.sh

# Or batch mode with feature flags
./scripts/setup.sh --batch \
  --server http://your-dashboard:5000 \
  --key YOUR_API_KEY \
  --no-commands      # Disable remote commands
```

### 3. Install Agent (Windows)

```powershell
# Run PowerShell as Administrator
.\agent\setup.ps1

# Or batch mode
.\agent\setup.ps1 -Batch -Server "http://dashboard:5000" -Key "YOUR_KEY"
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
│   ├── setup.sh              # Interactive Linux agent installer
│   ├── setup_dashboard.sh    # Interactive dashboard installer
│   ├── install_agent.sh      # Legacy agent installer
│   └── install_dashboard.sh  # Legacy dashboard installer
├── screenshots/        # Dashboard screenshots
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

# VM Monitor


A lightweight, self-hosted VM monitoring system with a Python agent and Flask-based web dashboard.

## Features

- **Real-time Monitoring**
  - Tracks CPU (Average/Instant), RAM, Disk (all partitions), Swap, and Network I/O.
  - Historical charts with selectable time ranges (1h, 24h, 7d, 30d).
  - Top Process monitoring (CPU/RAM consumers).

- **Multi-Platform Agent**
  - **Linux**: Supports RHEL, CentOS, Rocky, Oracle Linux, Ubuntu, Debian.
  - **Windows**: Native PowerShell-based installer, runs as a Scheduled Task.

- **Container & Kubernetes**
  - Auto-discovers **Docker** and **Podman** containers (including rootless).
  - Lists **Kubernetes Pods** running on the node (via CRI or filesystem scan).
  - View container logs and restart/stop/start containers from the dashboard.

- **Agent Auto-Updates**
  - Agents automatically poll the dashboard for new versions.
  - Updates are downloaded and applied securely without manual intervention.
  - Preserves configuration and restarts automatically.

- **Smart Alerting**
  - Visual badges for Warnings (80%+) and Critical (90%+) usage.
  - **SMS Notifications** via Twilio, Textbelt, or İleti Merkezi.
  - Configurable schedule (e.g., only send SMS during business hours).
  - Customizable timezones.

- **Remote Management**
  - Execute white-listed diagnostic tools (Ping, Disk Space, Uptime).
  - Manage system services (Systemd/Windows Services).
  - Reboot VMs or install system updates remotely.

- **Cloud Awareness**
  - Auto-detects cloud provider: AWS, GCP, Azure, Oracle Cloud.
  - Identifies hypervisors: Proxmox, VMware, Hyper-V, KVM.

## Quick Start

### 1. Deploy Dashboard

```bash
git clone https://github.com/aydinguven/vm-monitor.git
cd vm-monitor

# Interactive setup (recommended)
chmod +x scripts/*.sh
./scripts/setup_dashboard.sh

# Or batch mode
./scripts/setup_dashboard.sh --batch --api-key YOUR_KEY
```

### 2. Install Agent (Linux)

```bash
# Interactive setup
chmod +x scripts/*.sh
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

## Uninstall

To remove the agent or dashboard and clean up all files/configs:

```bash
# Remove Agent (Linux)
./scripts/cleanup_agent.sh

# Remove Dashboard (Linux)
./scripts/cleanup_dashboard.sh

# Uninstall Agent (Windows)
.\agent\cleanup.ps1
```

## Updating

To update to the latest version without losing data:

### Dashboard
1. Pull the latest changes: `git pull`
2. Run the update script: `sudo ./scripts/update_dashboard.sh`
   - *This will preserve your data (`vm_metrics.db`) and configuration.*

### Agents
**Automatic Updates (Recommended)**
If you enabled "Automatic Updates" during installation, your agents will automatically update themselves within 30 minutes of a dashboard update.

**Manual Update**
1. Pull the latest changes: `git pull`
2. Run the installer again: `./scripts/setup.sh` (Linux) or `.\agent\setup.ps1` (Windows)
3. Re-enter your Dashboard URL and API Key when prompted.

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
│   ├── cleanup_agent.sh      # Agent uninstaller
│   └── cleanup_dashboard.sh  # Dashboard uninstaller
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

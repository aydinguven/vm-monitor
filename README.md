# VM Monitor

A lightweight, self-hosted VM monitoring system with a Python agent and Flask-based web dashboard.

![Dashboard Overview](docs/images/dashboard_overview.png)

## ✨ Features

### Real-time Monitoring
- **System Metrics**: CPU (avg/instant), RAM, Disk (all partitions), Swap, Network I/O
- **Historical Charts**: 1h, 24h, 7d, 30d time ranges with interactive graphs
- **Process Tracking**: Top CPU/RAM consumers per VM

![VM Details](docs/images/vm_details.png)

### Multi-Platform Agent
| Platform | Installer | Runs As |
|----------|-----------|---------|
| **Linux** (RHEL, CentOS, Rocky, Oracle, Ubuntu, Debian) | `setup.sh` | Systemd service (`vm-agent` user) |
| **Windows** (Server 2016+, 10/11) | `setup.ps1` | Scheduled Task (SYSTEM) |

### Container & Kubernetes Discovery
- Auto-discovers **Docker** and **Podman** containers (including rootless)
- Lists **Kubernetes Pods** running on the node
- Manage containers: view logs, restart, stop, start

### Agent Auto-Updates
Agents poll the dashboard for new versions and update seamlessly:
1. Downloads new version from dashboard
2. Verifies integrity
3. Replaces agent binary
4. Restarts service automatically

### Smart Alerting
| Threshold | Badge | Action |
|-----------|-------|--------|
| 80%+ usage | ⚠️ Warning (Yellow) | Visual indicator |
| 90%+ usage | 🔴 Critical (Red) | SMS notification (if enabled) |

**SMS Providers**: Twilio, Textbelt, İleti Merkezi

### Remote Management
Execute white-listed diagnostic tools from the dashboard:
- **Diagnostics**: Ping, Disk Space, Uptime, Memory Info
- **Services**: View/Restart systemd or Windows services
- **System**: Reboot VM, Install updates

![Diagnostic Tools & Disk Usage](docs/images/disk_usage.png)

### Cloud Awareness
Auto-detects:
- **Cloud Providers**: AWS, GCP, Azure, Oracle Cloud
- **Hypervisors**: Proxmox, VMware, Hyper-V, KVM, WSL

### Mobile Optimized
Fully responsive with Dark/Light mode support.

| Dark Mode | Light Mode |
|-----------|------------|
| ![Mobile Dark](docs/images/mobile_dark.png) | ![Mobile Light](docs/images/mobile_light.png) |

---

## 🚀 Quick Start

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

![Installer Wizard](docs/images/installer_wizard.png)

```bash
# Option A: Clone and run
git clone https://github.com/aydinguven/vm-monitor.git
cd vm-monitor
./scripts/setup.sh

# Option B: One-liner (downloads from dashboard)
bash <(curl -sL https://your-dashboard/static/scripts/setup.sh)

# Option C: Batch mode with flags
./scripts/setup.sh --batch \
  --server https://your-dashboard \
  --key YOUR_API_KEY \
  --no-commands      # Disable remote commands
```

### 3. Install Agent (Windows)

```powershell
# Run PowerShell as Administrator
.\agent\setup.ps1

# Or batch mode
.\agent\setup.ps1 -Batch -Server "https://dashboard" -Key "YOUR_KEY"
```

---

## 🛠️ Configuration

### Dashboard Configuration

Configuration is stored in `instance/config.json`:

```json
{
  "api_key": "your-secure-api-key",
  "secret_key": "flask-session-secret",
  "database_url": "sqlite:///vm_metrics.db",
  "metric_retention_hours": 24
}
```

### Agent Configuration

Configuration is stored in `/opt/vm-agent/agent_config.json`:

```json
{
  "server_url": "https://your-dashboard",
  "api_key": "your-api-key",
  "interval": 30,
  "hostname": "my-server",
  "auto_update": true,
  "features": {
    "containers": true,
    "pods": true,
    "commands": true
  }
}
```

### Feature Flags (Dashboard)

Control dashboard-wide features via `instance/features.json`:

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

| Flag | Default | Description |
|------|---------|-------------|
| `commands` | `true` | **Remote Command Execution** - Allow running diagnostic tools and managing services from the dashboard. Disable if you only want monitoring without control. |
| `sms` | `true` | **SMS Notifications** - Enable sending SMS alerts via configured provider (Twilio, Textbelt, etc.). Requires `instance/sms_config.json`. |
| `alerts` | `true` | **Visual Alerts** - Show warning (80%+) and critical (90%+) badges on the dashboard. Disabling hides all alert indicators. |
| `containers` | `true` | **Container Discovery** - Collect and display Docker/Podman containers. Agents will still collect data but dashboard won't show it if disabled. |
| `pods` | `true` | **Kubernetes Pod Discovery** - Collect and display K8s pods running on nodes. Requires kubeconfig access on agents. |
| `auto_update` | `true` | **Agent Auto-Updates** - Allow agents to automatically download and install new versions from the dashboard. |

> **Note**: These are **dashboard-side** flags. Agent-side feature flags are in `agent_config.json` and are set during installation.

### SMS Configuration

Configure SMS alerts in `instance/sms_config.json`:

```json
{
  "provider": "twilio",
  "recipient": "+1234567890",
  "dashboard_url": "https://your-dashboard.com",
  "schedule": {
    "enabled": true,
    "timezone": "Europe/Istanbul",
    "start_hour": 9,
    "end_hour": 18,
    "days": ["mon", "tue", "wed", "thu", "fri"]
  },
  "twilio": {
    "account_sid": "ACxxxxxxxxx",
    "auth_token": "your-token",
    "from_number": "+1987654321"
  }
}
```

**Supported Providers**: `twilio`, `textbelt`, `iletimerkezi`, `disabled`

---

## 🔄 Updating

### Dashboard

```bash
cd vm-monitor
git pull
sudo ./scripts/update_dashboard.sh
```

This preserves your database (`vm_metrics.db`) and configuration files.

### Agents

**Automatic (Recommended)**: If auto-update is enabled, agents update themselves within 30 minutes of a dashboard update.

**Manual**:
```bash
git pull
./scripts/setup.sh   # Re-run installer
```

---

## 🗑️ Uninstalling

```bash
# Remove Agent (Linux)
./scripts/cleanup_agent.sh

# Remove Dashboard (Linux)
./scripts/cleanup_dashboard.sh

# Remove Agent (Windows - PowerShell as Admin)
.\agent\cleanup.ps1
```

---

## 🔐 Security

### Agent Security (v1.45+)
- Runs as dedicated `vm-agent` user (not root)
- Minimal sudo via `/etc/sudoers.d/vm-agent`
- Only detected binaries are granted sudo access

### Dashboard Security
- Strict file permissions (`750` directories, `640` files)
- Secrets in `instance/config.json` with `600` permissions
- Always use HTTPS in production

### Best Practices
1. Change the default API key immediately
2. Use a reverse proxy (Nginx/Caddy) with HTTPS
3. Restrict dashboard access via firewall rules
4. Regularly update both dashboard and agents

---

## 📡 API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/metrics` | POST | Agent metric submission |
| `/api/vms` | GET | List all VMs with latest metrics |
| `/api/vm/<hostname>/history` | GET | Historical metrics for a VM |
| `/api/command/<hostname>` | POST | Execute remote command |
| `/api/features` | GET/POST | View/update feature flags |
| `/api/sms-config` | GET/POST | View/update SMS configuration |
| `/api/send-sms` | POST | Manually trigger SMS test |

---

## 📁 Directory Structure

```
vm-monitor/
├── agent/                    # Monitoring agent
│   ├── agent.py              # Main agent script
│   ├── requirements.txt      # Python dependencies
│   └── setup.ps1             # Windows installer
├── dashboard/                # Flask web dashboard
│   ├── app.py                # Main Flask app
│   ├── config.py             # Configuration loader
│   ├── models.py             # Database models
│   ├── templates/            # Jinja2 templates
│   └── static/               # CSS, JS, images
├── scripts/                  # Installation scripts
│   ├── setup.sh              # Linux agent installer
│   ├── setup_dashboard.sh    # Dashboard installer
│   ├── update_dashboard.sh   # Dashboard updater
│   ├── cleanup_agent.sh      # Agent uninstaller
│   └── cleanup_dashboard.sh  # Dashboard uninstaller
├── instance/                 # Runtime config (gitignored)
│   ├── config.json           # Dashboard config
│   ├── features.json         # Feature flags
│   └── sms_config.json       # SMS settings
└── docs/                     # Documentation & images
```

---

## 📄 License

MIT License - See [LICENSE](LICENSE)

## 🤝 Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

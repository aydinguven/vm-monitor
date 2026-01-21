# Demo Mode

This directory contains everything needed to run a demo of VM Monitor with fake data.

## Quick Start

### Linux/macOS
```bash
chmod +x demo/run_demo.sh
./demo/run_demo.sh
```

### Windows (PowerShell)
```powershell
.\demo\run_demo.ps1
```

## What It Does

1. Creates a Python virtual environment
2. Installs dependencies
3. Generates 8 fake VMs with:
   - Different cloud providers (AWS, GCP, Oracle, Proxmox, etc.)
   - Varied resource usage (healthy, warning, critical)
   - Sample containers and Kubernetes pods
   - 24 hours of historical metrics
4. Launches the dashboard at http://localhost:5000

## Demo VMs

| Hostname | Provider | Status |
|----------|----------|--------|
| web-prod-01 | AWS | ✅ Healthy |
| db-master | Oracle Cloud | ⚠️ Warning (RAM) |
| k8s-worker-1 | GCP | ✅ Healthy (with pods) |
| backup-server | Proxmox | ✅ Healthy |
| monitor-critical | VMware | 🔴 Critical |
| dev-box | Hyper-V | ✅ Healthy |
| edge-node-asia | Azure | ✅ Healthy |
| storage-nas | Bare Metal | ✅ Healthy |

## Configuration

- **SMS**: Disabled
- **Auto-Update**: Disabled
- **Alerts**: Enabled (visual only)
- **Commands**: Enabled (won't actually execute)

## Files

- `generate_demo_data.py` - Creates fake database
- `config.json` - Demo dashboard config
- `features.json` - Feature flags
- `sms_config.json` - SMS disabled
- `run_demo.sh` - Linux/macOS launcher
- `run_demo.ps1` - Windows launcher

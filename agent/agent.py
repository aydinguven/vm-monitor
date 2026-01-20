#!/usr/bin/env python3
"""
VM Agent - Lightweight monitoring agent for Linux and Windows
Collects CPU, RAM, Disk, OS info, network, containers, and K8s pods.
"""

import json
import logging
import os
import platform
import random
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Optional

import psutil
import requests
from packaging import version

# OS Detection
IS_WINDOWS = platform.system() == "Windows"

# Import distro only on Linux (not available on Windows)
if not IS_WINDOWS:
    import distro

# =============================================================================
# Configuration
# =============================================================================

AGENT_VERSION = "1.41"
STRESS_DURATION = 75  # Duration in seconds for stress tests

# Server settings
SERVER_URL = os.getenv("VM_AGENT_SERVER", "http://localhost:5000")
API_KEY = os.getenv("VM_AGENT_KEY", "changeme")
PUSH_INTERVAL = int(os.getenv("VM_AGENT_INTERVAL", "15"))
HOSTNAME = os.getenv("VM_AGENT_HOSTNAME", socket.gethostname())

# Linux command whitelist
ALLOWED_COMMANDS_LINUX = {
    "ping": {
        "bin": "ping",
        "fixed_args": ["-c", "4"],
        "validate": r"^[a-zA-Z0-9.-]+$"
    },
    "uptime": {
        "bin": "uptime",
        "fixed_args": [],
        "validate": None
    },
    "disk_space": {
        "bin": "df",
        "fixed_args": ["-h"],
        "validate": None
    },
    "services": {
        "bin": "systemctl", 
        "fixed_args": ["list-units", "--type=service", "--state=running"],
        "validate": None
    },
    "check_service": {
        "bin": "systemctl",
        "fixed_args": ["is-active"],
        "validate": r"^[a-zA-Z0-9._-]+$"
    },
    "restart_vm": {
        "bin": "reboot",
        "fixed_args": [],
        "validate": None
    },
}

# Windows command whitelist
ALLOWED_COMMANDS_WINDOWS = {
    "ping": {
        "bin": "ping",
        "fixed_args": ["-n", "4"],
        "validate": r"^[a-zA-Z0-9.-]+$"
    },
    "uptime": {
        "bin": "powershell",
        "fixed_args": ["-Command", "(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime"],
        "validate": None
    },
    "disk_space": {
        "bin": "powershell",
        "fixed_args": ["-Command", "Get-PSDrive -PSProvider FileSystem | Format-Table Name,Used,Free,@{N='Size';E={$_.Used+$_.Free}}"],
        "validate": None
    },
    "services": {
        "bin": "powershell", 
        "fixed_args": ["-Command", "Get-Service | Where-Object Status -eq Running | Format-Table Name,DisplayName,Status"],
        "validate": None
    },
    "check_service": {
        "bin": "powershell",
        "fixed_args": ["-Command", "Get-Service"],
        "validate": r"^[a-zA-Z0-9._-]+$"
    },
    "restart_vm": {
        "bin": "shutdown",
        "fixed_args": ["/r", "/t", "5"],
        "validate": None
    },
}

# Cross-platform internal commands
INTERNAL_COMMANDS = {
    "update_agent": {"bin": "INTERNAL", "fixed_args": [], "validate": None},
    "system_update": {"bin": "INTERNAL", "fixed_args": [], "validate": None},
    "container_action": {"bin": "INTERNAL", "fixed_args": [], "validate": None},
    "stress_cpu": {"bin": "INTERNAL", "fixed_args": [], "validate": None},
    "stress_ram": {"bin": "INTERNAL", "fixed_args": [], "validate": None},
    "list_packages": {"bin": "INTERNAL", "fixed_args": [], "validate": None},
    "kill_process": {"bin": "INTERNAL", "fixed_args": [], "validate": r"^\d+(\s+\d+)?$"},
}

# Merge commands based on OS
ALLOWED_COMMANDS = {
    **(ALLOWED_COMMANDS_WINDOWS if IS_WINDOWS else ALLOWED_COMMANDS_LINUX),
    **INTERNAL_COMMANDS
}

# Update settings
UPDATE_URL = os.getenv("VM_AGENT_UPDATE_URL", "https://your-update-server.com")
UPDATE_CHECK_CYCLES = 60  # Check every 60 cycles (30min at 30s interval)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# =============================================================================
# Auto-Update Functions
# =============================================================================

def check_for_updates() -> bool:
    """Check for updates from the dashboard."""
    # Check env var first
    if os.getenv("VM_AGENT_AUTO_UPDATE", "true").lower() != "true":
        return False
        
    try:
        # Use SERVER_URL which points to the dashboard
        version_url = f"{SERVER_URL}/api/agent/version"
        logger.debug(f"Checking for updates at {version_url}")
        
        resp = requests.get(version_url, headers={"X-API-Key": API_KEY}, timeout=10)
        if resp.status_code != 200:
            return False

        data = resp.json()
        remote_version = data.get("version")
        
        if not remote_version:
            return False
            
        if version.parse(remote_version) > version.parse(AGENT_VERSION):
            logger.info(f"New version available: {remote_version} (current: {AGENT_VERSION})")
            return perform_update(remote_version, data)
            
    except Exception as e:
        logger.warning(f"Update check failed: {e}")
    
    return False


def perform_update(new_version: str, data: dict) -> bool:
    """Download and apply update."""
    import tempfile
    
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        temp_dir = tempfile.mkdtemp(prefix="vm-agent-update-")
        logger.debug(f"Using temp directory: {temp_dir}")
        
        # Dashboard provides relative URLs
        dl_url_path = data.get("download_url")
        req_url_path = data.get("requirements_url")
        
        if not dl_url_path:
            return False
            
        files_to_download = [("agent.py", dl_url_path)]
        if req_url_path:
            files_to_download.append(("requirements.txt", req_url_path))
        
        # Download files
        for fname, url_path in files_to_download:
            full_url = f"{SERVER_URL.rstrip('/')}/{url_path.lstrip('/')}"
            logger.info(f"Downloading {fname} from {full_url}...")
            
            resp = requests.get(full_url, headers={"X-API-Key": API_KEY}, timeout=20)
            if resp.status_code != 200:
                logger.error(f"Failed to download {fname}: {resp.status_code}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return False
            
            with open(os.path.join(temp_dir, fname), "wb") as f:
                f.write(resp.content)

        # Install new requirements
        if req_url_path:
            logger.info("Installing new requirements...")
            venv_pip = os.path.join(base_dir, "venv", "bin", "pip")
            if IS_WINDOWS:
                 venv_pip = os.path.join(base_dir, "venv", "Scripts", "pip.exe")
            
            pip_cmd = venv_pip if os.path.exists(venv_pip) else "pip3"
            if IS_WINDOWS and not os.path.exists(pip_cmd):
                 pip_cmd = "pip"
            
            try:
                subprocess.run(
                    [pip_cmd, "install", "-r", os.path.join(temp_dir, "requirements.txt")],
                    check=True, capture_output=True
                )
            except Exception as e:
                logger.warning(f"Requirements install warning: {e}")

        # Copy files to final location
        agent_dst = os.path.join(base_dir, "agent.py")
        
        # Windows: Rename running file to allow overwrite
        if IS_WINDOWS and os.path.exists(agent_dst):
            try:
                backup_path = agent_dst + ".old"
                if os.path.exists(backup_path):
                    os.remove(backup_path) # Remove old backup
                os.rename(agent_dst, backup_path)
            except OSError as e:
                logger.warning(f"Could not rename running agent.py (Windows): {e}")
                # Try overwrite anyway (might work if not strictly locked)

        for fname, _ in files_to_download:
            src = os.path.join(temp_dir, fname)
            dst = os.path.join(base_dir, fname)
            try:
                shutil.copy2(src, dst)
                logger.debug(f"Updated {dst}")
            except Exception as e:
                logger.error(f"Failed to copy {fname}: {e}")
                return False

        # Cleanup temp
        shutil.rmtree(temp_dir, ignore_errors=True)

        logger.info(f"Update to v{new_version} applied. Requesting restart...")
        return True

    except Exception as e:
        logger.error(f"Update failed: {e}")
    
    return False


# =============================================================================
# Metrics Collection
# =============================================================================

def get_cpu_metrics() -> dict:
    """Get CPU usage metrics."""
    cpu_instant = psutil.cpu_percent(interval=0)
    cpu_count = psutil.cpu_count()
    
    # Load average (1 min) converted to percentage
    try:
        load_avg = os.getloadavg()[0]
        cpu_avg = (load_avg / cpu_count) * 100
    except (AttributeError, OSError):
        cpu_avg = cpu_instant  # Windows fallback
    
    return {
        "cpu_avg": round(cpu_avg, 2),
        "cpu_instant": round(cpu_instant, 2),
        "cpu_count": cpu_count
    }


def get_memory_metrics() -> dict:
    """Get RAM usage metrics."""
    mem = psutil.virtual_memory()
    return {
        "ram_total_gb": round(mem.total / (1024 ** 3), 2),
        "ram_used_gb": round(mem.used / (1024 ** 3), 2),
        "ram_percent": round(mem.percent, 2)
    }


def get_disk_metrics() -> dict:
    """Get disk usage for all mounted partitions."""
    disk_usage = {}
    skip_fs = {"squashfs", "tmpfs", "devtmpfs"}
    
    for partition in psutil.disk_partitions(all=False):
        if partition.fstype in skip_fs:
            continue
        
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            disk_usage[partition.mountpoint] = {
                "total_gb": round(usage.total / (1024 ** 3), 2),
                "used_gb": round(usage.used / (1024 ** 3), 2),
                "percent": round(usage.percent, 2)
            }
        except (PermissionError, OSError):
            continue
    
    return disk_usage


def get_os_info() -> dict:
    """Get OS distribution, version, kernel, and architecture."""
    if IS_WINDOWS:
        os_name = f"Windows {platform.release()} {platform.win32_edition()}"
    else:
        os_name = distro.name(pretty=True) or platform.system()
    
    return {
        "os_name": os_name,
        "kernel": platform.release(),
        "arch": platform.machine()
    }


def get_network_info() -> dict:
    """Get primary internal and external IP addresses."""
    internal_ip = _get_internal_ip()
    external_ip = _get_external_ip()
    
    return {
        "ip_internal": internal_ip,
        "ip_external": external_ip
    }


def _get_internal_ip() -> Optional[str]:
    """Detect internal IP by connecting to external address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        pass
    
    # Fallback: first non-loopback IP
    for addrs in psutil.net_if_addrs().values():
        for addr in addrs:
            if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                return addr.address
    return None


def _get_external_ip() -> Optional[str]:
    """Get external IP from cloud metadata or public services."""
    # Cloud metadata endpoints (fastest)
    metadata_endpoints = [
        ("http://169.254.169.254/latest/meta-data/public-ipv4", {}),  # AWS
        ("http://169.254.169.254/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip",
         {"Metadata-Flavor": "Google"}),  # GCP
        ("http://169.254.169.254/opc/v1/vnics/", {}),  # OCI
    ]
    
    for url, headers in metadata_endpoints:
        try:
            resp = requests.get(url, headers=headers, timeout=1)
            if resp.status_code == 200 and resp.text:
                return resp.text.strip()
        except requests.RequestException:
            continue
    
    # Public IP services (fallback)
    ip_services = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com",
    ]
    
    for service in ip_services:
        try:
            resp = requests.get(service, timeout=3)
            if resp.status_code == 200:
                ip = resp.text.strip()
                if len(ip) < 45 and ("." in ip or ":" in ip):
                    return ip
        except requests.RequestException:
            continue
    
    return None


def get_cloud_provider() -> str:
    """Detect cloud provider/hypervisor from metadata and system info.
    
    Detection methods (in order of priority):
    1. Cloud metadata endpoints (AWS, GCP, Azure, Oracle Cloud)
    2. DMI/SMBIOS info (Proxmox, VMware, Hyper-V, KVM)
    3. Product name file
    """
    # 1. Try cloud metadata endpoints (fast timeout)
    cloud_checks = [
        # (URL, headers, provider_name)
        ("http://169.254.169.254/latest/meta-data/ami-id", {}, "AWS"),
        ("http://169.254.169.254/computeMetadata/v1/project/project-id", 
         {"Metadata-Flavor": "Google"}, "Google Cloud"),
        ("http://169.254.169.254/metadata/instance?api-version=2021-02-01", 
         {"Metadata": "true"}, "Azure"),
        ("http://169.254.169.254/opc/v1/instance/", {}, "Oracle Cloud"),
    ]
    
    for url, headers, provider in cloud_checks:
        try:
            resp = requests.get(url, headers=headers, timeout=0.5)
            if resp.status_code == 200:
                logger.debug(f"Detected cloud provider: {provider}")
                return provider
        except requests.RequestException:
            continue
    
    # 2. Windows: Check WMI for manufacturer/model
    if IS_WINDOWS:
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-WmiObject Win32_ComputerSystem).Manufacturer + ' ' + (Get-WmiObject Win32_ComputerSystem).Model"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                wmi_info = result.stdout.strip().lower()
                wmi_mapping = [
                    ("microsoft corporation virtual", "Hyper-V"),
                    ("vmware", "VMware"),
                    ("amazon ec2", "AWS"),
                    ("google", "Google Cloud"),
                    ("oracle", "Oracle Cloud"),
                    ("xen", "Xen"),
                    ("qemu", "QEMU/KVM"),
                    ("virtualbox", "VirtualBox"),
                ]
                for pattern, provider in wmi_mapping:
                    if pattern in wmi_info:
                        logger.debug(f"Detected provider from WMI: {provider}")
                        return provider
        except Exception:
            pass
    
    # 3. Linux: Check DMI/SMBIOS for hypervisor info
    dmi_files = [
        "/sys/class/dmi/id/product_name",
        "/sys/class/dmi/id/sys_vendor",
        "/sys/class/dmi/id/board_vendor",
        "/sys/class/dmi/id/bios_vendor",
    ]
    
    dmi_content = ""
    for dmi_file in dmi_files:
        if os.path.exists(dmi_file):
            try:
                with open(dmi_file, "r") as f:
                    dmi_content += f.read().lower() + " "
            except (PermissionError, OSError):
                pass
    
    # Map DMI strings to providers
    dmi_mapping = [
        ("proxmox", "Proxmox"),
        ("qemu", "Proxmox/KVM"),
        ("vmware", "VMware"),
        ("virtualbox", "VirtualBox"),
        ("microsoft corporation", "Hyper-V"),
        ("xen", "Xen"),
        ("amazon ec2", "AWS"),
        ("google compute", "Google Cloud"),
        ("oraclecloud", "Oracle Cloud"),
        ("openstack", "OpenStack"),
        ("digitalocean", "DigitalOcean"),
        ("linode", "Linode"),
        ("vultr", "Vultr"),
        ("hetzner", "Hetzner"),
    ]
    
    for pattern, provider in dmi_mapping:
        if pattern in dmi_content:
            logger.debug(f"Detected provider from DMI: {provider}")
            return provider
    
    # 3. Check /sys/hypervisor/type (Xen)
    hypervisor_file = "/sys/hypervisor/type"
    if os.path.exists(hypervisor_file):
        try:
            with open(hypervisor_file, "r") as f:
                hv_type = f.read().strip().lower()
                if hv_type == "xen":
                    return "Xen/AWS"
        except (PermissionError, OSError):
            pass
    
    # 4. Check for container/VM indicators
    if os.path.exists("/.dockerenv"):
        return "Docker"
    
    if os.path.exists("/run/systemd/container"):
        try:
            with open("/run/systemd/container", "r") as f:
                container_type = f.read().strip()
                return f"Container ({container_type})"
        except Exception:
            return "Container"
    
    # 5. Check systemd-detect-virt
    if shutil.which("systemd-detect-virt"):
        try:
            result = subprocess.run(
                ["systemd-detect-virt"], 
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0 and result.stdout.strip():
                virt = result.stdout.strip().lower()
                virt_mapping = {
                    "kvm": "KVM",
                    "qemu": "QEMU/KVM",
                    "vmware": "VMware",
                    "oracle": "VirtualBox",
                    "microsoft": "Hyper-V",
                    "xen": "Xen",
                    "amazon": "AWS",
                    "google": "Google Cloud",
                    "none": "Bare Metal",
                }
                for key, value in virt_mapping.items():
                    if key in virt:
                        return value
                return virt.capitalize()
        except Exception:
            pass
    
    return "Unknown"


def get_uptime() -> int:
    """Get system uptime in seconds."""
    return int(time.time() - psutil.boot_time())


def get_swap_usage() -> float:
    """Get swap memory usage percentage."""
    swap = psutil.swap_memory()
    return round(swap.percent, 1)


def get_network_io() -> dict:
    """Get network I/O bytes since boot."""
    net = psutil.net_io_counters()
    return {
        "bytes_sent": net.bytes_sent,
        "bytes_recv": net.bytes_recv
    }


def get_top_processes(n: int = 5) -> list:
    """Get top N processes by CPU and RAM usage."""
    procs = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            info = proc.info
            if info['cpu_percent'] is not None and info['memory_percent'] is not None:
                name = info['name']
                # Skip System Idle Process on Windows (it shows inverted CPU time)
                if IS_WINDOWS and name.lower() in ('system idle process', 'idle'):
                    continue
                # Cap CPU at 100% per core (handles psutil quirks)
                cpu_val = min(info['cpu_percent'], 100.0 * psutil.cpu_count())
                procs.append({
                    "pid": info['pid'],
                    "name": name[:30],
                    "cpu": round(cpu_val, 1),
                    "ram": round(info['memory_percent'], 1)
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    # Sort by CPU + RAM combined, return top N
    procs.sort(key=lambda x: x['cpu'] + x['ram'], reverse=True)
    return procs[:n]


def get_open_ports() -> list:
    """Get list of listening ports."""
    ports = []
    for conn in psutil.net_connections(kind='inet'):
        if conn.status == 'LISTEN':
            try:
                proc = psutil.Process(conn.pid) if conn.pid else None
                proc_name = proc.name()[:20] if proc else "unknown"
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                proc_name = "unknown"
            
            ports.append({
                "port": conn.laddr.port,
                "process": proc_name
            })
    
    # Remove duplicates and sort
    seen = set()
    unique_ports = []
    for p in ports:
        if p['port'] not in seen:
            seen.add(p['port'])
            unique_ports.append(p)
    
    return sorted(unique_ports, key=lambda x: x['port'])[:20]  # Limit to 20


def get_ssh_attempts() -> int:
    """Get count of failed login attempts (SSH on Linux, RDP/Logon on Windows)."""
    count = 0
    
    if IS_WINDOWS:
        # Query Windows Security Event Log for failed logon (Event ID 4625)
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-WinEvent -FilterHashtable @{LogName='Security';Id=4625} -MaxEvents 1000 -ErrorAction SilentlyContinue | Measure-Object).Count"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0 and result.stdout.strip():
                count = int(result.stdout.strip())
        except (subprocess.TimeoutExpired, ValueError, Exception):
            pass
        return count
    
    # Linux: Check auth logs
    log_files = ["/var/log/auth.log", "/var/log/secure"]
    
    for log_file in log_files:
        if not os.path.exists(log_file):
            continue
        try:
            result = subprocess.run(
                ["grep", "-c", "Failed password", log_file],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                count = int(result.stdout.strip())
                break
        except (subprocess.TimeoutExpired, ValueError):
            continue
    
    return count


def get_pending_updates() -> int:
    """Get count of pending OS updates."""
    
    if IS_WINDOWS:
        # Query Windows Update via COM object
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "(New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher().Search('IsInstalled=0 and IsHidden=0').Updates.Count"],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip())
        except (subprocess.TimeoutExpired, ValueError, Exception):
            pass
        return 0
    
    # Linux: Try yum/dnf first (RHEL/CentOS/Oracle)
    if shutil.which("dnf") or shutil.which("yum"):
        try:
            cmd = ["dnf", "check-update", "-q"] if shutil.which("dnf") else ["yum", "check-update", "-q"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            # Return code 100 means updates available, 0 means none
            if result.returncode == 100:
                # Count non-empty lines
                return len([l for l in result.stdout.strip().split('\n') if l.strip()])
            return 0
        except subprocess.TimeoutExpired:
            return -1
    
    # Try apt (Debian/Ubuntu)
    if shutil.which("apt"):
        try:
            result = subprocess.run(
                ["apt", "list", "--upgradable"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                lines = [l for l in result.stdout.strip().split('\n') if '/' in l]
                return len(lines)
        except subprocess.TimeoutExpired:
            return -1
    
    return 0


# =============================================================================
# Container & Kubernetes Discovery
# =============================================================================

def _get_uid(username: str) -> int:
    """Get UID for a username."""
    try:
        import pwd
        return pwd.getpwnam(username).pw_uid
    except (KeyError, ImportError):
        # Fallback: assume UID 1000+ for regular users
        return 1000


def get_containers() -> list:
    """Get running containers from Docker or Podman with detailed info.
    
    v1.28.6 - Also discovers rootless Podman containers by checking all users.
    """
    containers = []
    
    def run_container_cmd(runtime, user=None):
        """Run container list command, optionally as a specific user."""
        cmd = [runtime, "ps", "--format", "{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}\t{{.CreatedAt}}"]
        
        env = os.environ.copy()
        
        if user:
            # For rootless podman, we need to run as that user
            # and set XDG_RUNTIME_DIR
            cmd = ["sudo", "-u", user] + cmd
            env["XDG_RUNTIME_DIR"] = f"/run/user/{_get_uid(user)}"
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
                env=env
            )
            
            if result.returncode != 0:
                return []
            
            found = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) >= 3:
                    found.append({
                        "name": parts[0],
                        "image": parts[1],
                        "status": parts[2],
                        "ports": parts[3] if len(parts) > 3 else "",
                        "created": parts[4] if len(parts) > 4 else "",
                        "runtime": f"{runtime}" + (f" ({user})" if user else "")
                    })
            return found
        except (subprocess.TimeoutExpired, OSError):
            return []
    
    # 1. Check root-level Docker and Podman
    for runtime in ["docker", "podman"]:
        if shutil.which(runtime) is None:
            continue
        
        found = run_container_cmd(runtime)
        if found:
            containers.extend(found)
            logger.info(f"Found {len(found)} containers via {runtime}")
    
    # 2. Check rootless Podman for all users (v1.28.6)
    if shutil.which("podman"):
        users_to_check = []
        
        # Get list of regular users (UID >= 1000)
        if os.path.isdir("/home"):
            try:
                users_to_check = os.listdir("/home")
            except PermissionError:
                pass
        
        # Also check opc (Oracle Cloud)
        if "opc" not in users_to_check and os.path.isdir("/home/opc"):
            users_to_check.append("opc")
        
        for user in users_to_check:
            # Check if user has XDG_RUNTIME_DIR (indicates active session or lingering enabled)
            try:
                uid = _get_uid(user)
                runtime_dir = f"/run/user/{uid}"
                if os.path.isdir(runtime_dir):
                    found = run_container_cmd("podman", user=user)
                    if found:
                        containers.extend(found)
                        logger.info(f"Found {len(found)} rootless containers for user {user}")
            except Exception as e:
                logger.debug(f"Failed to check rootless podman for {user}: {e}")
    
    return containers


def get_pods() -> list:
    """Get running Kubernetes pods from all namespaces with detailed info.
    
    Dynamically discovers kubeconfigs from:
    - /etc/vm-agent/kubeconfigs/ (copied during install)
    - All user home directories (~/.kube/config)
    - Standard K8s paths (/etc/kubernetes/admin.conf, k3s, microk8s)
    - Root user's home
    """
    pods = []
    
    kubectl_cmds = [
        ["kubectl"],
        ["k3s", "kubectl"],
        ["microk8s", "kubectl"],
    ]
    
    # Extended columns: namespace, name, ready, status, restarts, age, node
    base_args = ["get", "pods", "-A", "--no-headers", "-o",
                 "custom-columns=NS:.metadata.namespace,NAME:.metadata.name,READY:.status.containerStatuses[*].ready,STATUS:.status.phase,RESTARTS:.status.containerStatuses[*].restartCount,AGE:.metadata.creationTimestamp,NODE:.spec.nodeName"]
    
    # Collect all potential kubeconfigs
    kubeconfigs = []
    seen = set()
    
    def add_config(path):
        if path and path not in seen and os.path.exists(path) and os.access(path, os.R_OK):
            kubeconfigs.append(path)
            seen.add(path)
            logger.debug(f"Found kubeconfig: {path}")
    
    # 1. Environment variable
    if os.getenv("KUBECONFIG"):
        add_config(os.getenv("KUBECONFIG"))
    
    # 2. Central directory (copied during install)
    kubeconfig_dir = "/etc/vm-agent/kubeconfigs"
    if os.path.isdir(kubeconfig_dir):
        try:
            for f in os.listdir(kubeconfig_dir):
                add_config(os.path.join(kubeconfig_dir, f))
        except PermissionError:
            pass
    
    # 3. Standard system K8s paths
    for path in [
        "/etc/kubernetes/admin.conf",
        "/etc/rancher/k3s/k3s.yaml",
        "/var/snap/microk8s/current/credentials/client.config",
        "/root/.kube/config",
    ]:
        add_config(path)
    
    # 4. All user home directories
    for home_base in ["/home", "/Users"]:  # Linux and macOS
        if os.path.isdir(home_base):
            try:
                for user in os.listdir(home_base):
                    add_config(f"{home_base}/{user}/.kube/config")
            except PermissionError:
                pass
    
    # 5. OCI/Oracle Cloud specific paths
    for path in [
        "/home/opc/.kube/config",
        "/home/opc/.oci/config",
        "/var/run/secrets/kubernetes.io/serviceaccount/token",  # In-cluster
    ]:
        add_config(path)
    
    if kubeconfigs:
        logger.info(f"Discovered {len(kubeconfigs)} kubeconfigs: {kubeconfigs}")
    
    for config_path in kubeconfigs:
        env = os.environ.copy()
        env["KUBECONFIG"] = config_path
        
        for cmd_prefix in kubectl_cmds:
            if shutil.which(cmd_prefix[0]) is None:
                continue
                
            try:
                result = subprocess.run(
                    cmd_prefix + base_args,
                    capture_output=True, text=True, timeout=10, env=env
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    for line in result.stdout.strip().split("\n"):
                        parts = line.split()
                        if len(parts) >= 4:
                            pods.append({
                                "namespace": parts[0],
                                "name": parts[1],
                                "ready": parts[2] if len(parts) > 2 else "",
                                "status": parts[3] if len(parts) > 3 else parts[2],
                                "restarts": parts[4] if len(parts) > 4 else "0",
                                "age": parts[5] if len(parts) > 5 else "",
                                "node": parts[6] if len(parts) > 6 else ""
                            })
                    
                    if pods:
                        logger.info(f"Found {len(pods)} pods using {config_path}")
                        return pods
                        
            except (subprocess.TimeoutExpired, OSError):
                continue
    
    # Fallback: crictl (for worker nodes without kubectl)
    if not pods and shutil.which("crictl"):
        # Try common sockets + default
        sockets = [
            "unix:///run/containerd/containerd.sock",
            "unix:///run/crio/crio.sock",
            "unix:///var/run/crio/crio.sock", 
            "unix:///run/k3s/containerd/containerd.sock",
            # Add more if needed
            None # Try without -r flag as last resort
        ]
        
        for sock in sockets:
            if pods: break # Stop if we found pods
            
            # Skip if socket file specifies path doesn't exist
            if sock and not os.path.exists(sock.replace("unix://", "")):
                continue
                
            try:
                cmd = ["crictl"]
                if sock:
                    cmd.extend(["-r", sock])
                cmd.extend(["pods", "-o", "json"])
                
                result = subprocess.run(
                    cmd,
                    capture_output=True, text=True, timeout=5
                )
                
                if result.returncode == 0:
                    try:
                        data = json.loads(result.stdout)
                        for item in data.get("items", []):
                            # crictl output mapping
                            metadata = item.get("metadata", {})
                            state = item.get("state", "UNKNOWN")
                            # created value in crictl is timestamp in ns
                            created_ns = item.get("createdAt", 0) 
                            created_dt = datetime.fromtimestamp(created_ns / 1e9, tz=timezone.utc)
                            age_str = created_dt.strftime("%Y-%m-%d %H:%M")
        
                            pods.append({
                                "namespace": metadata.get("namespace", "default"),
                                "name": metadata.get("name", "unknown"),
                                "ready": "True" if state == "SANDBOX_READY" else "False",
                                "status": state,
                                "restarts": "0", 
                                "age": age_str,
                                "node": HOSTNAME
                            })
                        
                        if pods:
                            logger.info(f"Found {len(pods)} pods via crictl ({sock or 'default'})")
                            return pods
                    except json.JSONDecodeError:
                        pass
                        
            except Exception as e:
                logger.debug(f"crictl failed ({sock}): {e}")

    # Fallback: Filesystem scan (if runtimes fail)
    if not pods and os.path.exists("/var/log/pods"):
        try:
            # Struct: /var/log/pods/NAMESPACE_NAME_UID/
            for entry in os.scandir("/var/log/pods"):
                if entry.is_dir():
                    try:
                        # Parsing "namespace_podname_uid"
                        # Warning: pod names can contain underscores, so we split cautiously
                        parts = entry.name.rsplit('_', 2)
                        if len(parts) >= 3:
                            ns = parts[0]
                            name = parts[1]
                            # UID is parts[2]
                            
                            stat = entry.stat()
                            created_dt = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc)
                            age_str = created_dt.strftime("%Y-%m-%d %H:%M")
                            
                            pods.append({
                                "namespace": ns,
                                "name": name,
                                "ready": "True", # Inferred
                                "status": "Running (FS)", # Inferred
                                "restarts": "0",
                                "age": age_str,
                                "node": HOSTNAME
                            })
                    except Exception:
                        continue
            
            if pods:
                logger.info(f"Found {len(pods)} pods via /var/log/pods")
                
        except Exception as e:
            logger.debug(f"FS scan failed: {e}")

    return pods


# =============================================================================
# Data Collection & Transmission
# =============================================================================

def collect_metrics() -> dict:
    """Collect all system metrics."""
    cpu = get_cpu_metrics()
    memory = get_memory_metrics()
    disk = get_disk_metrics()
    os_info = get_os_info()
    network = get_network_info()
    
    return {
        "hostname": HOSTNAME,
        "agent_version": AGENT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        # Cloud/Environment
        "cloud_provider": get_cloud_provider(),
        # CPU
        "cpu_avg": cpu["cpu_avg"],
        "cpu_instant": cpu["cpu_instant"],
        "cpu_count": cpu["cpu_count"],
        # Memory
        "ram_total_gb": memory["ram_total_gb"],
        "ram_used_gb": memory["ram_used_gb"],
        "ram_percent": memory["ram_percent"],
        # Disk
        "disk_usage": disk,
        # OS
        "os_name": os_info["os_name"],
        "kernel": os_info["kernel"],
        "arch": os_info["arch"],
        # Network
        "ip_internal": network["ip_internal"],
        "ip_external": network["ip_external"],
        # Uptime
        "uptime_seconds": get_uptime(),
        # Containers & Pods
        "containers": get_containers(),
        "pods": get_pods(),
        # v1.20 - New metrics
        "swap_percent": get_swap_usage(),
        "network_io": get_network_io(),
        "top_processes": get_top_processes(),
        "open_ports": get_open_ports(),
        "ssh_failed_attempts": get_ssh_attempts(),
        "pending_updates": get_pending_updates()
    }


def push_metrics(metrics: dict) -> bool:
    """Push metrics to the central server."""
    try:
        response = requests.post(
            f"{SERVER_URL}/api/metrics",
            json=metrics,
            headers={
                "X-API-Key": API_KEY,
                "Content-Type": "application/json"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            logger.debug("Metrics pushed successfully")
            
            # v1.22 - Process queued commands
            try:
                data = response.json()
                if "commands" in data:
                    for cmd in data["commands"]:
                        execute_command(cmd)
            except Exception as e:
                logger.error(f"Error processing server response: {e}")
                
            return True
        else:
            logger.warning(f"Server returned {response.status_code}: {response.text}")
            return False
            
    except requests.RequestException as e:
        logger.error(f"Failed to push metrics: {e}")
        return False


def run_stress_cpu(duration=STRESS_DURATION):
    """Generate CPU load for a specified duration."""
    end_time = time.time() + duration
    processes = []
    
    def cpu_load():
        while time.time() < end_time:
            _ = [x * x for x in range(1000)]

    # Spawn 2 threads to load CPU
    for _ in range(2):
        t = threading.Thread(target=cpu_load)
        t.daemon = True
        t.start()
        processes.append(t)
        
    for p in processes:
        p.join()

def run_stress_ram(duration=STRESS_DURATION):
    """Generate RAM load for a specified duration."""
    # Allocate ~512MB string
    try:
        data = " " * (512 * 1024 * 1024)
        time.sleep(duration)
        del data
    except MemoryError:
        pass

def execute_command(cmd_data: dict):
    """Execute a command securely if it's in the whitelist."""
    cmd_key = cmd_data.get("command")
    cmd_id = cmd_data.get("id")
    args = cmd_data.get("args", "")
    
    if cmd_key not in ALLOWED_COMMANDS:
        report_result(cmd_id, "failed", f"Command '{cmd_key}' not allowed")
        return

    config = ALLOWED_COMMANDS[cmd_key]
    
    # Handle Internal Commands (v1.23)
    if config["bin"] == "INTERNAL":
        if cmd_key == "update_agent":
            report_result(cmd_id, "running", "Checking for updates...")
            updated = check_for_updates()
            if updated:
                report_result(cmd_id, "completed", "Update found and applied. Agent restarting...")
                # Allow time to report before restart
                time.sleep(2)
                sys.exit(0) # Systemd will restart
            else:
                report_result(cmd_id, "completed", "No updates found. Agent is up to date.")
                
        elif cmd_key == "system_update":
            report_result(cmd_id, "running", "Detecting package manager...")
            update_cmd = []
            
            # Detect package manager
            if shutil.which("apt-get"):
                update_cmd = ["bash", "-c", "DEBIAN_FRONTEND=noninteractive apt-get update && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y"]
            elif shutil.which("dnf"):
                update_cmd = ["dnf", "update", "-y"]
            elif shutil.which("yum"):
                update_cmd = ["yum", "update", "-y"]
            else:
                report_result(cmd_id, "failed", "No supported package manager found (apt/dnf/yum)")
                return

            report_result(cmd_id, "running", f"Running system update ({update_cmd[0]}). This may take a while...")
            
            try:
                # 10 minute timeout for updates
                result = subprocess.run(
                    update_cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=600 
                )
                
                output = result.stdout + result.stderr
                if result.returncode == 0:
                    report_result(cmd_id, "completed", "Update successful. Rebooting system now...\n\n" + output[-500:]) # Show last 500 chars
                    time.sleep(3)
                    subprocess.run(["reboot"])
                else:
                    report_result(cmd_id, "failed", "Update failed:\n" + output)
            except subprocess.TimeoutExpired:
                report_result(cmd_id, "failed", "Update timed out after 10 minutes")
            except Exception as e:
                report_result(cmd_id, "failed", f"Error during update: {str(e)}")
            
        elif cmd_key == "container_action":
            # Args: runtime action id
            try:
                parts = args.split()
                if len(parts) != 3:
                    raise ValueError("Invalid arguments: expected 'runtime action id'")
                
                runtime, action, container_id = parts
                
                if runtime not in ["docker", "podman"]:
                    raise ValueError(f"Invalid runtime: {runtime}")
                
                if action not in ["restart", "stop", "start", "logs"]:
                    raise ValueError(f"Invalid action: {action}")
                    
                if not re.match(r"^[a-zA-Z0-9._-]+$", container_id):
                    raise ValueError("Invalid container ID format")
                
                cmd_list = [runtime, action]
                if action == "logs":
                    cmd_list.extend(["--tail", "100"])
                    
                cmd_list.append(container_id)
                
                report_result(cmd_id, "running", f"Executing {action} on {container_id}...")
                
                result = subprocess.run(
                    cmd_list, 
                    capture_output=True, 
                    text=True, 
                    timeout=15
                )
                
                status = "completed" if result.returncode == 0 else "failed"
                output = result.stdout + result.stderr
                report_result(cmd_id, status, output)
                
            except Exception as e:
                report_result(cmd_id, "failed", str(e))

        elif cmd_key == "stress_cpu":
            report_result(cmd_id, "running", f"Starting CPU stress test ({STRESS_DURATION}s)...")
            
            def stress_wrapper():
                try:
                    run_stress_cpu(75)
                    report_result(cmd_id, "completed", "CPU stress test completed")
                except Exception as e:
                    report_result(cmd_id, "failed", f"Stress test error: {e}")
            
            t = threading.Thread(target=stress_wrapper)
            t.daemon = True
            t.start()
            
        elif cmd_key == "stress_ram":
            report_result(cmd_id, "running", f"Starting RAM stress test ({STRESS_DURATION}s)...")
            
            def stress_wrapper():
                try:
                    run_stress_ram(STRESS_DURATION)
                    report_result(cmd_id, "completed", "RAM stress test completed")
                except Exception as e:
                    report_result(cmd_id, "failed", f"Stress test error: {e}")
            
            t = threading.Thread(target=stress_wrapper)
            t.daemon = True
            t.start()

        elif cmd_key == "list_packages":
            report_result(cmd_id, "running", "Querying package database...")
            
            try:
                cmd_list = []
                if shutil.which("rpm"):
                    # RPM: Name Version-Release
                    cmd_list = ["bash", "-c", "rpm -qa --qf '%{NAME}\t%{VERSION}-%{RELEASE}\n' | sort"]
                elif shutil.which("dpkg"):
                    # DEB: Name Version
                    cmd_list = ["dpkg-query", "-W", "-f=${Package}\t${Version}\n"]
                else:
                    report_result(cmd_id, "failed", "Unsupported OS: No rpm or dpkg found")
                    return

                result = subprocess.run(
                    cmd_list,
                    capture_output=True, text=True, timeout=30
                )
                
                if result.returncode == 0:
                    # Send output directly
                    report_result(cmd_id, "completed", result.stdout)
                else:
                    report_result(cmd_id, "failed", result.stderr)
            except Exception as e:
                report_result(cmd_id, "failed", str(e))

        elif cmd_key == "kill_process":
            # Args: PID [SIGNAL]
            try:
                parts = args.split()
                pid = int(parts[0])
                sig = int(parts[1]) if len(parts) > 1 else signal.SIGTERM
                
                # Only allow SIGTERM, SIGKILL, SIGINT
                if sig not in [signal.SIGTERM, signal.SIGKILL, signal.SIGINT]:
                    raise ValueError(f"Invalid signal: {sig}")

                os.kill(pid, sig)
                report_result(cmd_id, "completed", f"Sent signal {sig} to PID {pid}")
            except ValueError as e:
                report_result(cmd_id, "failed", f"Invalid PID or Signal: {e}")
            except ProcessLookupError:
                report_result(cmd_id, "failed", f"PID {pid} not found")
            except PermissionError:
                report_result(cmd_id, "failed", f"Permission denied killing PID {pid}")
            except Exception as e:
                report_result(cmd_id, "failed", f"Error: {str(e)}")
                
        return

    # Validate arguments
    if config["validate"] and args:
        if not re.match(config["validate"], args):
            report_result(cmd_id, "failed", "Invalid arguments detected")
            return
    elif config["validate"] is None and args:
         args = "" 
    
    # Construct command
    cmd_list = [config["bin"]] + config["fixed_args"]
    if args:
        cmd_list.append(args)
        
    try:
        logger.info(f"Executing command: {cmd_list}")
        result = subprocess.run(
            cmd_list, 
            capture_output=True, 
            text=True, 
            timeout=15
        )
        status = "completed" if result.returncode == 0 else "failed"
        output = result.stdout + result.stderr
        report_result(cmd_id, status, output)
        
    except subprocess.TimeoutExpired:
        report_result(cmd_id, "failed", "Command timed out")
    except Exception as e:
        report_result(cmd_id, "failed", str(e))


def report_result(cmd_id: int, status: str, output: str):
    """Report command execution result back to the server."""
    try:
        requests.post(
            f"{SERVER_URL}/api/commands/{cmd_id}/result",
            json={"status": status, "output": output},
            headers={"X-API-Key": API_KEY},
            timeout=5
        )
    except Exception as e:
        logger.error(f"Failed to report result for command {cmd_id}: {e}")


# =============================================================================
# Main Loop
# =============================================================================

def main():
    """Main loop - collect and push metrics."""
    try:
        logger.info(f"VM Agent v{AGENT_VERSION} starting")
        logger.info(f"Hostname: {HOSTNAME} | Server: {SERVER_URL} | Interval: {PUSH_INTERVAL}s")
        
        # Prime CPU cache
        psutil.cpu_percent(interval=1)
        
        # Initial update check
        if check_for_updates():
            logger.info("Update applied during startup. Restarting...")
            os.execv(sys.executable, [sys.executable] + sys.argv)
        
        update_counter = 0
        consecutive_failures = 0
        max_failures = 10
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        sys.exit(1)
    
    while True:
        try:
            # Periodic update check
            update_counter += 1
            if update_counter >= UPDATE_CHECK_CYCLES:
                if check_for_updates():
                    logger.info("Auto-update applied. Restarting...")
                    os.execv(sys.executable, [sys.executable] + sys.argv)
                update_counter = 0

            metrics = collect_metrics()
            logger.debug(f"Collected: {json.dumps(metrics, indent=2)}")
            
            if push_metrics(metrics):
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                
            if consecutive_failures >= max_failures:
                logger.warning(f"Failed {max_failures}x consecutively, backing off...")
                time.sleep(PUSH_INTERVAL * 5)
                consecutive_failures = 0
            else:
                time.sleep(PUSH_INTERVAL)
                
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            time.sleep(PUSH_INTERVAL)


if __name__ == "__main__":
    main()


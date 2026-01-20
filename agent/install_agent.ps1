# install_agent.ps1 - Windows VM Agent Installer
# Usage: .\install_agent.ps1 -Server "http://DASHBOARD:5000" -Key "YOUR_API_KEY"

param(
    [Parameter(Mandatory = $true)]
    [string]$Server,
    
    [Parameter(Mandatory = $true)]
    [string]$Key,
    
    [int]$Interval = 15,
    [string]$InstallDir = "C:\vm-agent"
)

$ErrorActionPreference = "Stop"

Write-Host "[INFO] Installing VM Agent for Windows..." -ForegroundColor Green

# Find Python - try py, python, python3 in order
$pythonCmd = $null
foreach ($cmd in @("py", "python", "python3")) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        $pythonCmd = $cmd
        break
    }
}

if (-not $pythonCmd) {
    Write-Host "[ERROR] Python not found. Please install from python.org and ensure 'Add Python to PATH' is checked." -ForegroundColor Red
    Write-Host "[TIP] You can also try running: winget install Python.Python.3.11" -ForegroundColor Yellow
    exit 1
}

Write-Host "[INFO] Using Python: $pythonCmd" -ForegroundColor Cyan

# Create install directory
Write-Host "[INFO] Creating installation directory..." -ForegroundColor Green
if (Test-Path $InstallDir) { Remove-Item $InstallDir -Recurse -Force }
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

# Download agent files
Write-Host "[INFO] Downloading agent files..." -ForegroundColor Green
$UpdateUrl = "https://your-update-server.com"
Invoke-WebRequest -Uri "$UpdateUrl/agent/agent.py" -OutFile "$InstallDir\agent.py"
Invoke-WebRequest -Uri "$UpdateUrl/agent/requirements.txt" -OutFile "$InstallDir\requirements.txt"

# Create virtual environment
Write-Host "[INFO] Setting up Python environment..." -ForegroundColor Green
Set-Location $InstallDir
& $pythonCmd -m venv venv

# Install dependencies (use Windows-specific requirements without distro)
.\venv\Scripts\pip.exe install --upgrade pip -q
.\venv\Scripts\pip.exe install psutil requests packaging -q

# Create config file
Write-Host "[INFO] Creating configuration..." -ForegroundColor Green
@"
VM_AGENT_SERVER=$Server
VM_AGENT_KEY=$Key
VM_AGENT_INTERVAL=$Interval
VM_AGENT_UPDATE_URL=$UpdateUrl
"@ | Out-File -FilePath "$InstallDir\vm-agent.conf" -Encoding ASCII

# Create startup script
$startScript = @"
@echo off
cd /d $InstallDir
for /f "tokens=*" %%a in (vm-agent.conf) do set %%a
call venv\Scripts\activate
python agent.py
"@
Set-Content -Path "$InstallDir\start_agent.bat" -Value $startScript -Encoding ASCII

# Create Windows Service using NSSM if available, otherwise scheduled task
$nssmPath = Get-Command nssm -ErrorAction SilentlyContinue
if ($nssmPath) {
    Write-Host "[INFO] Creating Windows service with NSSM..." -ForegroundColor Green
    nssm install VMAgent "$InstallDir\start_agent.bat"
    nssm set VMAgent DisplayName "VM Monitoring Agent"
    nssm set VMAgent Description "Lightweight VM monitoring agent"
    nssm set VMAgent Start SERVICE_AUTO_START
    Start-Service VMAgent
}
else {
    Write-Host "[INFO] Creating scheduled task (NSSM not found)..." -ForegroundColor Yellow
    
    # Create a PowerShell wrapper for better control
    $wrapperScript = @"
Set-Location '$InstallDir'
`$env:VM_AGENT_SERVER = '$Server'
`$env:VM_AGENT_KEY = '$Key'
`$env:VM_AGENT_INTERVAL = '$Interval'
`$env:VM_AGENT_UPDATE_URL = '$UpdateUrl'
& .\venv\Scripts\python.exe agent.py
"@
    Set-Content -Path "$InstallDir\run_agent.ps1" -Value $wrapperScript -Encoding UTF8
    
    # Create scheduled task that runs at startup
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$InstallDir\run_agent.ps1`""
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    
    Register-ScheduledTask -TaskName "VMAgent" -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
    Start-ScheduledTask -TaskName "VMAgent"
}

Write-Host ""
Write-Host "[SUCCESS] VM Agent installed!" -ForegroundColor Green
Write-Host "Server: $Server" -ForegroundColor Cyan
Write-Host "Install Dir: $InstallDir" -ForegroundColor Cyan
Write-Host ""
Write-Host "To check status:" -ForegroundColor Gray
Write-Host "  Get-ScheduledTask -TaskName VMAgent" -ForegroundColor Gray
Write-Host "To view logs, run start_agent.bat manually" -ForegroundColor Gray


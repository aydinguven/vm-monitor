# setup.ps1 - Interactive VM Agent Installer for Windows
# Usage: .\setup.ps1                    (interactive mode)
#        .\setup.ps1 -Batch [options]   (non-interactive mode)

param(
    [switch]$Batch,
    [string]$Server = "",
    [string]$Key = "",
    [int]$Interval = 30,
    [switch]$NoContainers,
    [switch]$NoPods,
    [switch]$NoCommands,
    [switch]$NoAutoUpdate,
    [string]$InstallDir = "C:\vm-agent"
)

$ErrorActionPreference = "Stop"

# Feature flags
$FeatureContainers = -not $NoContainers
$FeaturePods = -not $NoPods
$FeatureCommands = -not $NoCommands
$FeatureAutoUpdate = -not $NoAutoUpdate

function Write-Banner {
    Write-Host ""
    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host "           VM Monitoring Agent - Setup Wizard             " -ForegroundColor Cyan
    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Read-HostRequired {
    param([string]$Prompt, [string]$Default = "")
    
    if ($Default) {
        $input = Read-Host "$Prompt [$Default]"
        if ([string]::IsNullOrWhiteSpace($input)) { return $Default }
        return $input
    }
    
    do {
        $input = Read-Host $Prompt
        if ([string]::IsNullOrWhiteSpace($input)) {
            Write-Host "  This field is required." -ForegroundColor Red
        }
    } while ([string]::IsNullOrWhiteSpace($input))
    
    return $input
}

function Read-YesNo {
    param([string]$Prompt, [bool]$Default = $true)
    
    $hint = if ($Default) { "[Y/n]" } else { "[y/N]" }
    $input = Read-Host "$Prompt $hint"
    
    if ([string]::IsNullOrWhiteSpace($input)) { return $Default }
    return $input -match "^[Yy]"
}

function Show-FeatureStatus {
    param([string]$Name, [bool]$Enabled)
    
    if ($Enabled) {
        Write-Host "  $Name`: " -NoNewline
        Write-Host "[Enabled]" -ForegroundColor Green
    }
    else {
        Write-Host "  $Name`: " -NoNewline
        Write-Host "[Disabled]" -ForegroundColor Red
    }
}

function Run-Interactive {
    Write-Banner
    
    Write-Host "Step 1: Dashboard Connection" -ForegroundColor Green
    Write-Host "----------------------------" -ForegroundColor DarkGray
    $script:Server = Read-HostRequired -Prompt "Dashboard URL (e.g., http://monitor.example.com:5000)"
    $script:Key = Read-HostRequired -Prompt "API Key"
    $script:Interval = [int](Read-HostRequired -Prompt "Collection interval (seconds)" -Default "30")
    
    Write-Host ""
    Write-Host "Step 2: Feature Configuration" -ForegroundColor Green
    Write-Host "----------------------------" -ForegroundColor DarkGray
    Write-Host "Enable or disable optional features:" -ForegroundColor Yellow
    Write-Host ""
    
    $script:FeatureContainers = Read-YesNo -Prompt "Enable container discovery (Docker)?" -Default $true
    $script:FeaturePods = Read-YesNo -Prompt "Enable Kubernetes pod discovery?" -Default $true
    $script:FeatureCommands = Read-YesNo -Prompt "Enable remote command execution?" -Default $true
    $script:FeatureAutoUpdate = Read-YesNo -Prompt "Enable automatic agent updates?" -Default $true
    
    Write-Host ""
    Write-Host "Step 3: Confirm Settings" -ForegroundColor Green
    Write-Host "----------------------------" -ForegroundColor DarkGray
    Write-Host "  Server:     " -NoNewline; Write-Host $Server -ForegroundColor Cyan
    Write-Host "  API Key:    " -NoNewline; Write-Host "$($Key.Substring(0,4))****" -ForegroundColor Cyan
    Write-Host "  Interval:   " -NoNewline; Write-Host "${Interval}s" -ForegroundColor Cyan
    Show-FeatureStatus -Name "Containers" -Enabled $FeatureContainers
    Show-FeatureStatus -Name "K8s Pods  " -Enabled $FeaturePods
    Show-FeatureStatus -Name "Commands  " -Enabled $FeatureCommands
    Show-FeatureStatus -Name "Auto-Update" -Enabled $FeatureAutoUpdate
    Write-Host ""
    
    $confirm = Read-YesNo -Prompt "Proceed with installation?" -Default $true
    if (-not $confirm) {
        Write-Host "Installation cancelled." -ForegroundColor Yellow
        exit 0
    }
}

function Install-Agent {
    Write-Host ""
    Write-Host "[-] Installing VM Agent..." -ForegroundColor Green
    
    # 1. Check Python
    Write-Host "[1/5] Checking Python installation..." -ForegroundColor Blue
    $pythonCmd = $null
    foreach ($cmd in @("py", "python", "python3")) {
        if (Get-Command $cmd -ErrorAction SilentlyContinue) {
            $pythonCmd = $cmd
            break
        }
    }
    
    if (-not $pythonCmd) {
        Write-Host "Python not found. Please install from python.org" -ForegroundColor Red
        Write-Host "Tip: winget install Python.Python.3.11" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "  Using Python: $pythonCmd" -ForegroundColor Cyan
    
    # 2. Create install directory
    Write-Host "[2/5] Creating installation directory..." -ForegroundColor Blue
    if (Test-Path $InstallDir) {
        Remove-Item $InstallDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    
    # 3. Copy agent files
    Write-Host "[3/5] Installing agent code..." -ForegroundColor Blue
    # Robust path detection
    if ($PSScriptRoot) {
        $ScriptPath = $PSScriptRoot
    }
    else {
        $ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
    }
    
    # If still null (e.g. some manual invocation contexts), assume current dir if agent.py exists
    if (-not $ScriptPath) {
        $ScriptPath = Get-Location
    }

    $SourceRoot = Split-Path -Parent $ScriptPath
    
    # Check if we're in the agent directory or scripts directory
    if (Test-Path (Join-Path $ScriptPath "agent.py")) {
        # We're in the agent directory
        Copy-Item (Join-Path $ScriptPath "agent.py") $InstallDir
        Copy-Item (Join-Path $ScriptPath "requirements*.txt") $InstallDir -ErrorAction SilentlyContinue
    }
    elseif (Test-Path (Join-Path $SourceRoot "agent")) {
        # We're in scripts directory, copy from agent folder
        Copy-Item (Join-Path $SourceRoot "agent\*") $InstallDir -Recurse
    }
    else {
        Write-Host "Cannot find agent source files." -ForegroundColor Red
        exit 1
    }
    
    # 4. Setup Python environment
    Write-Host "[4/5] Setting up Python environment..." -ForegroundColor Blue
    Set-Location $InstallDir
    & $pythonCmd -m venv venv
    .\venv\Scripts\pip.exe install --upgrade pip -q
    
    # Install Windows-specific dependencies (no distro package)
    if (Test-Path "requirements-windows.txt") {
        .\venv\Scripts\pip.exe install -r requirements-windows.txt -q
    }
    else {
        .\venv\Scripts\pip.exe install psutil requests packaging -q
    }
    
    # 5. Create configuration (JSON)
    Write-Host "[5/5] Generating configuration..." -ForegroundColor Blue
    
    $jsonConfig = @{
        "server_url"  = $Server
        "api_key"     = $Key
        "interval"    = [int]$Interval
        "hostname"    = [System.Net.Dns]::GetHostName()
        "auto_update" = $FeatureAutoUpdate
        "features"    = @{
            "containers" = $FeatureContainers
            "pods"       = $FeaturePods
            "commands"   = $FeatureCommands
        }
    }
    
    $jsonConfig | ConvertTo-Json -Depth 3 | Out-File -FilePath "$InstallDir\agent_config.json" -Encoding ASCII
    
    # Create PowerShell runner script
    $runScript = @"
Set-Location '$InstallDir'
& .\venv\Scripts\python.exe agent.py
"@
    Set-Content -Path "$InstallDir\run_agent.ps1" -Value $runScript -Encoding UTF8
    
    # Create scheduled task
    $existingTask = Get-ScheduledTask -TaskName "VMAgent" -ErrorAction SilentlyContinue
    if ($existingTask) {
        Unregister-ScheduledTask -TaskName "VMAgent" -Confirm:$false
    }
    
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$InstallDir\run_agent.ps1`""
    $trigger = New-ScheduledTaskTrigger -AtStartup
    # Run as NetworkService (Hardening v1.44)
    # Grant permissions to install dir first
    $acl = Get-Acl $InstallDir
    $accessRule = New-Object System.Security.AccessControl.FileSystemAccessRule("Network Service", "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow")
    $acl.SetAccessRule($accessRule)
    Set-Acl $InstallDir $acl
    
    $principal = New-ScheduledTaskPrincipal -UserId "NETWORK SERVICE" -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 365)
    
    Register-ScheduledTask -TaskName "VMAgent" -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
    Start-ScheduledTask -TaskName "VMAgent"
    
    Write-Host ""
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host "               Agent installed successfully!              " -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Config:  " -NoNewline; Write-Host "$InstallDir\agent_config.json" -ForegroundColor Cyan
    Write-Host "  Status:  " -NoNewline; Write-Host "Get-ScheduledTask -TaskName VMAgent" -ForegroundColor Cyan
    Write-Host "  Logs:    " -NoNewline; Write-Host "Run $InstallDir\run_agent.ps1 manually" -ForegroundColor Cyan
    Write-Host ""
}

# Main
if (-not $Batch) {
    Run-Interactive
}
else {
    if ([string]::IsNullOrWhiteSpace($Server)) {
        Write-Host "Error: -Server is required in batch mode" -ForegroundColor Red
        exit 1
    }
    if ([string]::IsNullOrWhiteSpace($Key)) {
        Write-Host "Error: -Key is required in batch mode" -ForegroundColor Red
        exit 1
    }
}

Install-Agent

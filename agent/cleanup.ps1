# cleanup.ps1 - Remove VM Agent from Windows
# Usage: .\cleanup.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "              VM Agent - Cleanup Script                   " -ForegroundColor Cyan  
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

$confirm = Read-Host "This will remove VM Agent completely. Are you sure? [y/N]"
if ($confirm -notmatch "^[Yy]") {
    Write-Host "Cancelled." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "[-] Removing VM Agent..." -ForegroundColor Green

# 1. Stop and remove scheduled task
Write-Host "  Stopping scheduled task..." -ForegroundColor Cyan
$task = Get-ScheduledTask -TaskName "VMAgent" -ErrorAction SilentlyContinue
if ($task) {
    Stop-ScheduledTask -TaskName "VMAgent" -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName "VMAgent" -Confirm:$false
    Write-Host "  * Removed scheduled task" -ForegroundColor Green
}

# 2. Stop any running agent processes
Write-Host "  Stopping agent processes..." -ForegroundColor Cyan
Get-Process -Name "python*" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*agent.py*"
} | Stop-Process -Force -ErrorAction SilentlyContinue

# 3. Remove NSSM service if exists
$nssmService = Get-Service -Name "VMAgent" -ErrorAction SilentlyContinue
if ($nssmService) {
    Write-Host "  Stopping NSSM service..." -ForegroundColor Cyan
    Stop-Service -Name "VMAgent" -Force -ErrorAction SilentlyContinue
    if (Get-Command nssm -ErrorAction SilentlyContinue) {
        nssm remove VMAgent confirm
    }
    else {
        sc.exe delete VMAgent
    }
    Write-Host "  * Removed NSSM service" -ForegroundColor Green
}

# 4. Remove application files
Write-Host "  Removing application files..." -ForegroundColor Cyan
$installDir = "C:\vm-agent"
if (Test-Path $installDir) {
    # Try multiple times to handle file locking
    $maxRetries = 5
    $retryCount = 0
    $removed = $false
    
    while (-not $removed -and $retryCount -lt $maxRetries) {
        try {
            Remove-Item $installDir -Recurse -Force -ErrorAction Stop
            $removed = $true
            Write-Host "  * Removed $installDir" -ForegroundColor Green
        }
        catch {
            Write-Host "  ! File locked, retrying in 2s... ($($retryCount+1)/$maxRetries)" -ForegroundColor Yellow
            # Try to kill leftovers again
            Get-Process -Name "python*" -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$installDir*" } | Stop-Process -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
            $retryCount++
        }
    }
    
    if (-not $removed) {
        Write-Host "  [WARNING] Could not remove some files (likely locked). Please restart and try again." -ForegroundColor Red
    }
}

# 5. Clean up temp files
Remove-Item "$env:TEMP\vm-agent*" -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "                  Cleanup complete!                       " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""

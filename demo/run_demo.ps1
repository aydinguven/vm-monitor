# VM Monitor Demo
# Run this in PowerShell

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "🚀 VM Monitor Demo" -ForegroundColor Cyan
Write-Host "==================" -ForegroundColor Cyan

# Check for Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Host "❌ Python is required but not found" -ForegroundColor Red
  exit 1
}

# Create venv if needed
$VenvPath = Join-Path $ScriptDir "venv"
if (-not (Test-Path $VenvPath)) {
  Write-Host "📦 Creating virtual environment..." -ForegroundColor Yellow
  python -m venv $VenvPath
}

# Activate venv
& "$VenvPath\Scripts\Activate.ps1"

# Install dependencies
Write-Host "📥 Installing dependencies..." -ForegroundColor Yellow
pip install -q flask flask-sqlalchemy flask-migrate gunicorn apscheduler requests pytz

# Generate demo data
Write-Host "🔧 Generating demo data..." -ForegroundColor Yellow
python "$ScriptDir\generate_demo_data.py"

# Copy config files to instance dir
$InstanceDir = Join-Path $ProjectRoot "dashboard\instance"
New-Item -ItemType Directory -Force -Path $InstanceDir | Out-Null
Copy-Item "$ScriptDir\config.json" $InstanceDir -Force
Copy-Item "$ScriptDir\features.json" $InstanceDir -Force
Copy-Item "$ScriptDir\sms_config.json" $InstanceDir -Force

# Copy demo database
Copy-Item "$ScriptDir\demo_db.sqlite" $InstanceDir -Force

# Update database URL in config
@"
{
  "secret_key": "demo-secret-key-not-for-production",
  "api_key": "demo-api-key",
  "database_url": "sqlite:///instance/demo_db.sqlite",
  "timezone": "UTC"
}
"@ | Set-Content "$InstanceDir\config.json"

Write-Host ""
Write-Host "✅ Demo ready!" -ForegroundColor Green
Write-Host ""
Write-Host "📌 Starting dashboard at: http://localhost:5000" -ForegroundColor Cyan
Write-Host "   Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

# Run dashboard
Set-Location "$ProjectRoot\dashboard"
python app.py

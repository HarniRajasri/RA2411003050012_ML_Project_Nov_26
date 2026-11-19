<# Starts the KHorizon backend (API + WebSocket + dashboard if built). Stop with Ctrl+C. #>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$venvPy = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) { Write-Host "Run .\scripts\setup_windows.ps1 first." -ForegroundColor Red; exit 1 }

# Read host/port from .env (defaults 0.0.0.0:8000). 0.0.0.0 lets the ESP32 reach this PC over Wi-Fi.
$hostName = "0.0.0.0"; $port = "8000"
if (Test-Path (Join-Path $Root ".env")) {
  foreach ($line in Get-Content (Join-Path $Root ".env")) {
    if ($line -match "^\s*BACKEND_HOST\s*=\s*(\S+)") { $hostName = $Matches[1] }
    if ($line -match "^\s*BACKEND_PORT\s*=\s*(\d+)") { $port = $Matches[1] }
  }
}
Set-Location (Join-Path $Root "backend")
Write-Host "KHorizon backend on http://localhost:$port  (API docs: /docs)   Ctrl+C to stop" -ForegroundColor Green
& $venvPy -m uvicorn app.main:create_app --factory --host $hostName --port $port

<# Starts the backend in a new window and opens the dashboard in your browser. #>
$Root = Split-Path -Parent $PSScriptRoot
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $PSScriptRoot "start_backend.ps1")
Write-Host "Backend starting in a new window..."
Start-Sleep -Seconds 4
Start-Process "http://localhost:8000"
& (Join-Path $PSScriptRoot "show_ip.ps1")

<# Lets the ESP32 reach the backend through Windows Firewall (TCP port 8000, private networks only).
   Run once, as Administrator:   powershell -ExecutionPolicy Bypass -File .\scripts\allow_firewall.ps1 #>
param([int]$Port = 8000)
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { Write-Host "Please run this script from a PowerShell window opened with 'Run as administrator'." -ForegroundColor Red; exit 1 }
$name = "KHorizon backend (TCP $Port)"
if (Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue) { Write-Host "Rule already exists." -ForegroundColor Yellow; exit 0 }
New-NetFirewallRule -DisplayName $name -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -Profile Private | Out-Null
Write-Host "Firewall rule added for TCP $Port on Private networks." -ForegroundColor Green
Write-Host "If your Wi-Fi is set to 'Public' in Windows, change it to 'Private' (Settings > Network) or the ESP32 will still be blocked."

<#
  KHorizon one-time setup for Windows (PowerShell).
  Run from the project root:   powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
  Options:  -WithEeg   also install MNE/NumPy/SciPy for EEG feature extraction
            -SkipFrontend   skip npm install/build (the backend still runs; a prebuilt dashboard may be included)
#>
param([switch]$WithEeg, [switch]$SkipFrontend)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Step($m) { Write-Host "`n== $m" -ForegroundColor Cyan }
function Fail($m) { Write-Host "ERROR: $m" -ForegroundColor Red; exit 1 }

Step "Checking Python (3.11 or newer)"
$pyExe = $null; $pyPre = @()
$candidates = @(
  @{ Exe = "py"; Pre = @("-3") },
  @{ Exe = "python"; Pre = @() },
  @{ Exe = "python3"; Pre = @() }
)
foreach ($c in $candidates) {
  if (-not (Get-Command $c.Exe -ErrorAction SilentlyContinue)) { continue }
  $probe = @($c.Pre) + @("-c", "import sys; print('%d.%d' % sys.version_info[:2])")
  $v = & $c.Exe @probe 2>$null
  if ($LASTEXITCODE -ne 0 -or -not $v) { continue }
  $parts = ("$v").Trim().Split(".")
  if ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 11) { $pyExe = $c.Exe; $pyPre = @($c.Pre); Write-Host "Found Python $v ($($c.Exe))"; break }
}
if (-not $pyExe) { Fail "Python 3.11+ not found. Install it from https://www.python.org/downloads/ and tick 'Add python.exe to PATH'." }

Step "Creating virtual environment (.venv)"
if (-not (Test-Path ".venv\Scripts\python.exe")) { & $pyExe @pyPre -m venv .venv; if ($LASTEXITCODE -ne 0) { Fail "Could not create the virtual environment." } }
$venvPy = Join-Path $Root ".venv\Scripts\python.exe"

Step "Installing backend packages"
& $venvPy -m pip install --upgrade pip | Out-Null
& $venvPy -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { Fail "pip could not install the backend requirements. Check your internet connection." }
if ($WithEeg) {
  Step "Installing EEG packages (MNE, NumPy, SciPy)"
  & $venvPy -m pip install -r eeg\requirements.txt
  if ($LASTEXITCODE -ne 0) { Fail "pip could not install the EEG requirements." }
}

Step "Creating .env"
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host "Created .env from .env.example" } else { Write-Host ".env already exists - left unchanged" }

if (-not $SkipFrontend) {
  Step "Building the dashboard (Node.js 18+ required)"
  $node = Get-Command node -ErrorAction SilentlyContinue
  if (-not $node) {
    if (Test-Path "frontend\dist\index.html") { Write-Host "Node.js not found, but a prebuilt dashboard is included - continuing." -ForegroundColor Yellow }
    else { Fail "Node.js not found. Install the LTS version from https://nodejs.org/ and run this script again." }
  } else {
    Push-Location frontend
    npm install --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { Pop-Location; Fail "npm install failed." }
    npm run build
    if ($LASTEXITCODE -ne 0) { Pop-Location; Fail "npm run build failed." }
    Pop-Location
  }
}

Step "Running the automated tests"
Push-Location backend
& $venvPy -m pytest
$testExit = $LASTEXITCODE
Pop-Location
if ($testExit -ne 0) { Write-Host "Some tests failed - see above. The prototype may still run; please report the failure." -ForegroundColor Yellow }

Write-Host "`nSetup complete." -ForegroundColor Green
Write-Host "Next:  .\scripts\start_backend.ps1      then open http://localhost:8000"
Write-Host "Real headband: run .\scripts\show_ip.ps1 and .\scripts\allow_firewall.ps1 (as Administrator), then see docs\hardware.md"

<# Optional: runs the dashboard in development mode on http://localhost:5173 (needs Node.js and the backend running).
   You do NOT need this if the dashboard is already built - the backend serves it on http://localhost:8000. #>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $Root "frontend")
if (-not (Test-Path "node_modules")) { npm install --no-audit --no-fund }
npm run dev

$Root = Split-Path -Parent $PSScriptRoot
$venvPy = Join-Path $Root ".venv\Scripts\python.exe"
Set-Location (Join-Path $Root "backend")
& $venvPy -m pytest
Set-Location $Root
& $venvPy -c "import numpy, scipy" 2>$null
if ($LASTEXITCODE -eq 0) { & $venvPy -m pytest eeg -q } else { Write-Host "EEG tests skipped (install with setup_windows.ps1 -WithEeg)." }

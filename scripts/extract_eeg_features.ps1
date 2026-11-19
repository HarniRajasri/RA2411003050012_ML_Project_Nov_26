<# Turns a recorded BDF file into the feature CSV that the backend replays (needs setup_windows.ps1 -WithEeg).
   Default input:  EEG\Experiment2\sub-01_ses-01_task-stim01_eeg.bdf  inside the project folder.
   Example:  .\scripts\extract_eeg_features.ps1 -InputFile "E:\College-projects\KHorizon\EEG\Experiment2\sub-01_ses-01_task-stim01_eeg.bdf" #>
param([string]$InputFile = "", [string]$OutputFile = "")
$Root = Split-Path -Parent $PSScriptRoot
$venvPy = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) { Write-Host "Run .\scripts\setup_windows.ps1 -WithEeg first." -ForegroundColor Red; exit 1 }
& $venvPy -c "import mne" 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "MNE is not installed. Run .\scripts\setup_windows.ps1 -WithEeg" -ForegroundColor Red; exit 1 }
Set-Location (Join-Path $Root "eeg")
$args2 = @("feature_extraction.py")
if ($InputFile) { $args2 += @("--input", $InputFile) }
if ($OutputFile) { $args2 += @("--output", $OutputFile) }
& $venvPy @args2
if ($LASTEXITCODE -eq 0) { Write-Host "`nNow set EEG_MODE=DATASET_REPLAY in .env and restart the backend." -ForegroundColor Green }

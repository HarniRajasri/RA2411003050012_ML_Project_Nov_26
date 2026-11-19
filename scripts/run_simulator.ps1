<# Standalone simulated students talking to the running backend over HTTP.
   Example:  .\scripts\run_simulator.ps1 -Students 25 -Duration 600 -Flaky #>
param([int]$Students = 20, [int]$Duration = 0, [switch]$Flaky, [string]$Url = "http://localhost:8000")
$Root = Split-Path -Parent $PSScriptRoot
$venvPy = Join-Path $Root ".venv\Scripts\python.exe"
$a = @("simulator\student_simulator.py", "--url", $Url, "--students", $Students, "--duration", $Duration)
if ($Flaky) { $a += "--flaky" }
Set-Location $Root
& $venvPy @a

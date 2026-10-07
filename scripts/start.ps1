# Start Myelin in the background (no console window).
#   powershell -ExecutionPolicy Bypass -File scripts\start.ps1

$root = Split-Path -Parent $PSScriptRoot
$pythonw = "$root\backend\.venv\Scripts\pythonw.exe"
$url = "http://127.0.0.1:8765"

if (-not (Test-Path $pythonw)) {
  Write-Host "Myelin isn't set up yet. Run scripts\setup.ps1 first."
  exit 1
}

function Test-Running {
  try { Invoke-RestMethod "$url/api/health" -TimeoutSec 1 | Out-Null; return $true } catch { return $false }
}

if (Test-Running) {
  Write-Host "Myelin is already running at $url"
} else {
  Start-Process -FilePath $pythonw -ArgumentList "-m", "myelin" -WorkingDirectory "$root\backend" -WindowStyle Hidden
  foreach ($i in 1..20) { if (Test-Running) { break }; Start-Sleep -Milliseconds 500 }
  if (-not (Test-Running)) {
    Write-Host "Myelin didn't start. Check the log at $env:LOCALAPPDATA\Myelin\myelin.log"
    exit 1
  }
  Write-Host "Myelin is running at $url"
}

# First run: open settings so prayer times can use your location.
$settings = Invoke-RestMethod "$url/api/settings"
if (-not $settings.has_location) { Start-Process "$url/settings" }

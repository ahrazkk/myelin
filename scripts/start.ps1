# Open the Myelin app from source (window, tray icon, hotkey and the wallpaper's server).
#   powershell -ExecutionPolicy Bypass -File scripts\start.ps1
# Most people install Myelin with the installer from GitHub Releases instead.

$root = Split-Path -Parent $PSScriptRoot
$pythonw = "$root\backend\.venv\Scripts\pythonw.exe"

if (-not (Test-Path $pythonw)) {
  Write-Host "Myelin isn't set up yet. Run scripts\setup.ps1 first."
  exit 1
}

Start-Process -FilePath $pythonw -ArgumentList "-m", "myelin.desktop" -WorkingDirectory "$root\backend"
Write-Host "Myelin is opening. Closing its window keeps it in the tray; quit from the tray icon."
Write-Host "Press Ctrl+Alt+M anywhere to tell Myelin about your day."

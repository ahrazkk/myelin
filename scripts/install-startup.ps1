# Start Myelin (from source) in the tray every time you sign in to Windows.
# You can also switch this on and off in Myelin's Settings, under App.

$root = Split-Path -Parent $PSScriptRoot
$pythonw = "$root\backend\.venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonw)) {
  Write-Host "Myelin isn't set up yet. Run scripts\setup.ps1 first."
  exit 1
}

# Older versions used a Startup-folder shortcut; replace it with the same registry entry the app uses.
$oldShortcut = Join-Path ([Environment]::GetFolderPath("Startup")) "Myelin.lnk"
if (Test-Path $oldShortcut) { Remove-Item $oldShortcut }

$command = "`"$pythonw`" -m myelin.desktop --background"
New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "Myelin" -Value $command `
  -PropertyType String -Force | Out-Null

Write-Host "Myelin will start in the tray when you sign in."

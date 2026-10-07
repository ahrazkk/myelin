# Start Myelin automatically every time you sign in to Windows.
# Undo it by deleting "Myelin" from the Startup folder (Win+R, then shell:startup).

$root = Split-Path -Parent $PSScriptRoot
$pythonw = "$root\backend\.venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonw)) {
  Write-Host "Myelin isn't set up yet. Run scripts\setup.ps1 first."
  exit 1
}

$shortcut = Join-Path ([Environment]::GetFolderPath("Startup")) "Myelin.lnk"
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($shortcut)
$link.TargetPath = $pythonw
$link.Arguments = "-m myelin"
$link.WorkingDirectory = "$root\backend"
$link.Description = "Myelin: habit wallpaper server"
$link.Save()

Write-Host "Myelin will now start when you sign in. Shortcut: $shortcut"

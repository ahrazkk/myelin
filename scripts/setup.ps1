# One-time setup for Myelin on Windows.
# From the repo folder, run:
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

function Refresh-Path {
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
              [Environment]::GetEnvironmentVariable("Path", "User")
}

function Find-Python {
  if (Get-Command py -ErrorAction SilentlyContinue) { return @("py", "-3") }
  if (Get-Command python -ErrorAction SilentlyContinue) {
    $v = & python -c "import sys; print(sys.version_info >= (3, 11))" 2>$null
    if ($v -eq "True") { return @("python") }
  }
  return $null
}

# Python 3.11+ and Node.js, installed with winget when missing
$python = Find-Python
if (-not $python) {
  Write-Host "Installing Python 3.12..."
  winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
  Refresh-Path
  $python = Find-Python
  if (-not $python) { throw "Python was installed but isn't on PATH yet. Close this window, open a new one and run setup again." }
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  Write-Host "Installing Node.js LTS..."
  winget install --id OpenJS.NodeJS.LTS -e --accept-source-agreements --accept-package-agreements
  Refresh-Path
  if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "Node.js was installed but isn't on PATH yet. Close this window, open a new one and run setup again." }
}

Write-Host "Setting up the Python server..."
Push-Location "$root\backend"
$exe, $pyArgs = $python
& $exe @pyArgs -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
& .\.venv\Scripts\python.exe -m pip install -e ".[desktop]" --quiet
Pop-Location

Write-Host "Building the wallpaper..."
Push-Location "$root\frontend"
npm ci --no-audit --no-fund
npm run build
Pop-Location

Write-Host ""
Write-Host "Myelin is set up. Next:"
Write-Host "  1. scripts\start.ps1            opens the Myelin app"
Write-Host "  2. scripts\install-startup.ps1  starts it in the tray every time you sign in"
Write-Host "  3. In Lively Wallpaper, add http://127.0.0.1:8765/ as a web wallpaper"

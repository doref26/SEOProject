Param(
    [switch]$NoBackend,
    [switch]$NoFrontend
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Project root: $root"

if (-not $NoBackend) {
    Write-Host "Starting backend (FastAPI) in a new PowerShell window..."
    $backendCmd = "-NoLogo -NoExit -Command cd `"$root`"; python -m backend.main"
    Start-Process powershell $backendCmd
}

if (-not $NoFrontend) {
    Write-Host "Starting frontend (Vite + React) in a new PowerShell window..."
    $frontendRoot = Join-Path $root "frontend"
    $frontendCmd = "-NoLogo -NoExit -Command cd `"$frontendRoot`"; npm run dev"
    Start-Process powershell $frontendCmd
}

Write-Host "Done. Separate windows should now be running the backend and frontend."



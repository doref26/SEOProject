Param(
    [switch]$SkipPython,
    [switch]$SkipNode
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "Project root: $root"

if (-not $SkipPython) {
    Write-Host ""
    Write-Host "=== Python environment & backend requirements ===" -ForegroundColor Cyan

    $venvPath = Join-Path $root ".venv"
    if (-not (Test-Path $venvPath)) {
        Write-Host "Creating virtual environment at $venvPath ..."
        python -m venv $venvPath
    } else {
        Write-Host "Virtual environment already exists at $venvPath"
    }

    $venvPython = Join-Path $venvPath "Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        Write-Warning "Could not find python executable in .venv. Make sure Python is installed correctly."
    } else {
        Write-Host "Upgrading pip in the virtual environment..."
        & $venvPython -m pip install --upgrade pip

        $reqPath = Join-Path $root "backend\requirements.txt"
        if (Test-Path $reqPath) {
            Write-Host "Installing backend requirements from $reqPath ..."
            & $venvPython -m pip install -r $reqPath
        } else {
            Write-Warning "backend\requirements.txt not found, skipping Python dependency installation."
        }
    }
}

if (-not $SkipNode) {
    Write-Host ""
    Write-Host "=== Node.js dependencies for frontend ===" -ForegroundColor Cyan
    $frontendRoot = Join-Path $root "frontend"
    if (Test-Path $frontendRoot) {
        Push-Location $frontendRoot
        try {
            Write-Host "Running 'npm install' in $frontendRoot ..."
            npm install
        } finally {
            Pop-Location
        }
    } else {
        Write-Warning "frontend directory not found, skipping npm install."
    }
}

Write-Host ""
Write-Host "Setup completed. You can now run '.\run_project.ps1' from the project root to start the app." -ForegroundColor Green



# ==============================================================================
# scripts/demo-preflight.ps1: Read-Only Environment and Port Preflight Check
# ==============================================================================
# Verifies Docker, Python virtual environment, Node.js/npm, frontend dependencies,
# database configuration presence, compose config, and port availability (8000, 3001).
#
# Read-only: Makes NO persistent changes and terminates NO processes.
# Returns exit code 0 on complete pass, or exit code 1 on any check failure.
# ==============================================================================

[CmdletBinding()]
param()

$ErrorActionPreference = "Continue"

# 1. Resolve repository root from script location
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backendVenvPython = Join-Path $repoRoot "backend\.venv\Scripts\python.exe"
$frontendNodeModules = Join-Path $repoRoot "frontend\node_modules\next"
$composeFile = Join-Path $repoRoot "compose.yaml"
$rootEnvFile = Join-Path $repoRoot ".env"
$backendEnvFile = Join-Path $repoRoot "backend\.env"

$hasFailure = $false

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " DispenseIQ Demo Preflight Check (Read-Only)" -ForegroundColor Cyan
Write-Host " Repository Root: $repoRoot" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ------------------------------------------------------------------------------
# Check 1: Docker CLI availability
# ------------------------------------------------------------------------------
$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerCmd) {
    Write-Host "[PASS] Docker CLI: Available ($($dockerCmd.Source))" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Docker CLI: Not found on PATH." -ForegroundColor Red
    Write-Host "       Action: Install Docker Desktop and ensure 'docker.exe' is in PATH." -ForegroundColor Yellow
    $hasFailure = $true
}

# ------------------------------------------------------------------------------
# Check 2: Docker Engine responsiveness
# ------------------------------------------------------------------------------
if ($dockerCmd) {
    $dockerVersionOutput = ((& docker version --format "{{.Server.Version}}" 2>&1) | Out-String).Trim()
    if ($LASTEXITCODE -eq 0 -and $dockerVersionOutput) {
        Write-Host "[PASS] Docker Engine: Available (version $dockerVersionOutput)" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] Docker Engine: Not running or unresponsive." -ForegroundColor Red
        Write-Host "       Output: $dockerVersionOutput" -ForegroundColor Yellow
        Write-Host "       Action: Launch Docker Desktop and wait for the Linux container engine to be ready." -ForegroundColor Yellow
        Write-Host "       If the error mentions '//./pipe/dockerDesktopLinuxEngine', Docker Desktop is still booting." -ForegroundColor Yellow
        $hasFailure = $true
    }
}

# ------------------------------------------------------------------------------
# Check 3: Docker Compose configuration
# ------------------------------------------------------------------------------
if (Test-Path $composeFile) {
    if ($dockerCmd) {
        $composeConfigOutput = ((& docker compose -f "$composeFile" config 2>&1) | Out-String).Trim()
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[PASS] Docker Compose: Valid configuration ($composeFile)" -ForegroundColor Green
        } else {
            Write-Host "[FAIL] Docker Compose: Invalid compose.yaml configuration." -ForegroundColor Red
            Write-Host "       Output: $composeConfigOutput" -ForegroundColor Yellow
            $hasFailure = $true
        }
    }
} else {
    Write-Host "[FAIL] Docker Compose: compose.yaml not found at $composeFile" -ForegroundColor Red
    $hasFailure = $true
}

# ------------------------------------------------------------------------------
# Check 4: Backend Python virtual environment
# ------------------------------------------------------------------------------
if (Test-Path $backendVenvPython) {
    $pyVer = ((& "$backendVenvPython" --version 2>&1) | Out-String).Trim()
    Write-Host "[PASS] Backend Python: Found ($pyVer at backend\.venv\Scripts\python.exe)" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Backend Python: Not found at $backendVenvPython" -ForegroundColor Red
    Write-Host "       Action: In 'backend/', create virtual environment:" -ForegroundColor Yellow
    Write-Host "               python -m venv .venv" -ForegroundColor Yellow
    Write-Host "               .\.venv\Scripts\python.exe -m pip install -e `".[dev]`"" -ForegroundColor Yellow
    $hasFailure = $true
}

# ------------------------------------------------------------------------------
# Check 5: Node.js and npm
# ------------------------------------------------------------------------------
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
$npmCmd = Get-Command npm -ErrorAction SilentlyContinue

if ($nodeCmd) {
    $nodeVer = ((& node --version 2>&1) | Out-String).Trim()
    Write-Host "[PASS] Node.js: Available ($nodeVer)" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Node.js: Not found on PATH." -ForegroundColor Red
    Write-Host "       Action: Install Node.js (v18+ recommended)." -ForegroundColor Yellow
    $hasFailure = $true
}

if ($npmCmd) {
    $npmVer = ((& npm --version 2>&1) | Out-String).Trim()
    Write-Host "[PASS] npm: Available (v$npmVer)" -ForegroundColor Green
} else {
    Write-Host "[FAIL] npm: Not found on PATH." -ForegroundColor Red
    $hasFailure = $true
}

# ------------------------------------------------------------------------------
# Check 6: Frontend dependencies (node_modules/next)
# ------------------------------------------------------------------------------
if (Test-Path $frontendNodeModules) {
    Write-Host "[PASS] Frontend dependencies: Installed (frontend\node_modules\next present)" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Frontend dependencies: Missing." -ForegroundColor Red
    Write-Host "       Action: In 'frontend/', install dependencies:" -ForegroundColor Yellow
    Write-Host "               npm install" -ForegroundColor Yellow
    $hasFailure = $true
}

# ------------------------------------------------------------------------------
# Check 7: Database configuration presence (DATABASE_URL presence/absence only)
# ------------------------------------------------------------------------------
$dbUrlConfigured = $false
$dbUrlSource = ""

if (-not [string]::IsNullOrWhiteSpace($env:DATABASE_URL)) {
    $dbUrlConfigured = $true
    $dbUrlSource = "Environment variable `$env:DATABASE_URL"
} elseif (Test-Path $rootEnvFile) {
    $rootEnvContent = Get-Content $rootEnvFile -ErrorAction SilentlyContinue
    if ($rootEnvContent -match "^\s*DATABASE_URL\s*=") {
        $dbUrlConfigured = $true
        $dbUrlSource = ".env file in repository root"
    }
}

if (-not $dbUrlConfigured -and (Test-Path $backendEnvFile)) {
    $backendEnvContent = Get-Content $backendEnvFile -ErrorAction SilentlyContinue
    if ($backendEnvContent -match "^\s*DATABASE_URL\s*=") {
        $dbUrlConfigured = $true
        $dbUrlSource = "backend\.env file"
    }
}

if ($dbUrlConfigured) {
    Write-Host "[PASS] DATABASE_URL: Configured ($dbUrlSource)" -ForegroundColor Green
} else {
    Write-Host "[FAIL] DATABASE_URL: Not configured." -ForegroundColor Red
    Write-Host "       Action: Set `$env:DATABASE_URL in PowerShell session or create .env from .env.example." -ForegroundColor Yellow
    Write-Host "       Example: `$env:DATABASE_URL = `"postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens`"" -ForegroundColor Yellow
    $hasFailure = $true
}

# ------------------------------------------------------------------------------
# Check 8: Port availability for startup (Port 8000 and Port 3001)
# ------------------------------------------------------------------------------
$portsToCheck = @(
    @{ Port = 8000; Service = "FastAPI Backend" },
    @{ Port = 3001; Service = "Next.js Frontend (agreed demo port)" }
)

foreach ($pInfo in $portsToCheck) {
    $targetPort = $pInfo.Port
    $serviceName = $pInfo.Service
    $listeners = Get-NetTCPConnection -LocalPort $targetPort -State Listen -ErrorAction SilentlyContinue

    if ($listeners) {
        $owningPids = $listeners | Select-Object -ExpandProperty OwningProcess -Unique
        $procDescriptions = @()
        foreach ($pidVal in $owningPids) {
            $pObj = Get-Process -Id $pidVal -ErrorAction SilentlyContinue
            $pName = if ($pObj) { $pObj.ProcessName } else { "Unknown" }
            $procDescriptions += "PID $pidVal ($pName)"
        }
        $procString = $procDescriptions -join ", "
        Write-Host "[FAIL] Port $targetPort ($serviceName): OCCUPIED by $procString" -ForegroundColor Red
        Write-Host "       Action: Stop or reconfigure the occupying process before starting DispenseIQ." -ForegroundColor Yellow
        Write-Host "       Note: Preflight does NOT kill external processes automatically." -ForegroundColor Yellow
        Write-Host "       Note: Port 3000 is outside the project startup contract and must not be substituted." -ForegroundColor Yellow
        $hasFailure = $true
    } else {
        Write-Host "[PASS] Port $targetPort ($serviceName): Available" -ForegroundColor Green
    }
}

# ------------------------------------------------------------------------------
# Final summary and next step
# ------------------------------------------------------------------------------
Write-Host ""
if ($hasFailure) {
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host " PREFLIGHT FAILED: Please resolve the issues reported above." -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
    exit 1
} else {
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host " PREFLIGHT PASSED: Environment is ready for demo startup." -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next command to run:" -ForegroundColor Cyan
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\start-db.ps1" -ForegroundColor Cyan
    exit 0
}

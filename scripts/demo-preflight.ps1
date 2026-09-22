# ==============================================================================
# scripts/demo-preflight.ps1: Read-Only Environment and Port Preflight Check
# ==============================================================================
# Verifies Docker, Python virtual environment, Node.js (>=20.9.0), frontend dependencies,
# non-blank database configuration presence, compose config, and port availability (8000, 3001).
#
# Read-only: Makes NO persistent changes and terminates NO processes.
# Returns exit code 0 on complete pass, or exit code 1 on any check failure.
# ==============================================================================

[CmdletBinding()]
param(
    # Optional parameters for dependency-free verification testing
    [string]$OverrideNodeVersion = $null,
    [string]$OverrideDatabaseUrl = $null,
    [string]$OverrideRootEnvPath = $null,
    [string]$OverrideBackendEnvPath = $null
)

$ErrorActionPreference = "Continue"

# ------------------------------------------------------------------------------
# Helper Functions (Exported for dependency-free unit testing)
# ------------------------------------------------------------------------------

function Test-NodeVersionSupported([string]$versionString, [string]$minRequired = "20.9.0") {
    if ([string]::IsNullOrWhiteSpace($versionString)) { return $false }
    $clean = $versionString.Trim() -replace '^[vV]', ''
    try {
        $parsed = [version]$clean
        $min = [version]$minRequired
        return ($parsed -ge $min)
    } catch {
        return $false
    }
}

function Get-DatabaseConfigStatus(
    [string]$envVal,
    [string]$rootEnvPath,
    [string]$backendEnvPath
) {
    if (-not [string]::IsNullOrWhiteSpace($envVal)) {
        return [PSCustomObject]@{
            Configured = $true
            Source = "Environment variable `$env:DATABASE_URL"
        }
    }

    $targets = @(
        @{ Path = $rootEnvPath; Label = ".env file in repository root" },
        @{ Path = $backendEnvPath; Label = "backend\.env file" }
    )

    foreach ($target in $targets) {
        if ($target.Path -and (Test-Path $target.Path)) {
            $lines = Get-Content $target.Path -ErrorAction SilentlyContinue
            if ($lines) {
                foreach ($line in $lines) {
                    $trimmed = $line.Trim()
                    if ($trimmed.StartsWith("#") -or -not ($trimmed -match '^\s*DATABASE_URL\s*=\s*(.*)$')) {
                        continue
                    }
                    $rawVal = $matches[1].Trim()
                    # Strip surrounding quotes if present
                    if (($rawVal.StartsWith('"') -and $rawVal.EndsWith('"')) -or ($rawVal.StartsWith("'") -and $rawVal.EndsWith("'"))) {
                        if ($rawVal.Length -ge 2) {
                            $rawVal = $rawVal.Substring(1, $rawVal.Length - 2).Trim()
                        }
                    }
                    if (-not [string]::IsNullOrWhiteSpace($rawVal)) {
                        return [PSCustomObject]@{
                            Configured = $true
                            Source = $target.Label
                        }
                    }
                }
            }
        }
    }

    return [PSCustomObject]@{
        Configured = $false
        Source = "None"
    }
}

# 1. Resolve repository root from script location
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backendVenvPythonCandidates = @(
    @{ Path = (Join-Path $repoRoot "backend\.venv\Scripts\python.exe"); Label = "backend\.venv\Scripts\python.exe" },
    @{ Path = (Join-Path $repoRoot ".venv\Scripts\python.exe"); Label = ".venv\Scripts\python.exe" },
    @{ Path = (Join-Path $repoRoot "backend\.venv\bin\python.exe"); Label = "backend\.venv\bin\python.exe" },
    @{ Path = (Join-Path $repoRoot ".venv\bin\python.exe"); Label = ".venv\bin\python.exe" }
)

$backendVenvPython = $null
$backendVenvLabel = "backend\.venv\Scripts\python.exe"
foreach ($candidate in $backendVenvPythonCandidates) {
    if (Test-Path $candidate.Path) {
        $backendVenvPython = $candidate.Path
        $backendVenvLabel = $candidate.Label
        break
    }
}
if (-not $backendVenvPython) {
    $backendVenvPython = Join-Path $repoRoot "backend\.venv\Scripts\python.exe"
}

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
    Write-Host "[PASS] Backend Python: Found ($pyVer at $backendVenvLabel)" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Backend Python: Not found at $backendVenvPython" -ForegroundColor Red
    Write-Host "       Action: Create virtual environment (.venv or backend\.venv):" -ForegroundColor Yellow
    Write-Host "               python -m venv .venv" -ForegroundColor Yellow
    Write-Host "               .\.venv\Scripts\python.exe -m pip install -e `".[dev]`"" -ForegroundColor Yellow
    $hasFailure = $true
}

# ------------------------------------------------------------------------------
# Check 5: Node.js (>=20.9.0 required by Next.js 16) and npm
# ------------------------------------------------------------------------------
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
$npmCmd = Get-Command npm -ErrorAction SilentlyContinue

$nodeVerRaw = if ($OverrideNodeVersion) { $OverrideNodeVersion } elseif ($nodeCmd) { ((& node --version 2>&1) | Out-String).Trim() } else { $null }

if ($nodeVerRaw) {
    $isNodeValid = Test-NodeVersionSupported $nodeVerRaw "20.9.0"
    if ($isNodeValid) {
        Write-Host "[PASS] Node.js: Available ($nodeVerRaw, >= 20.9.0)" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] Node.js: Unsupported version ($nodeVerRaw). Node.js >=20.9.0 is required by Next.js 16." -ForegroundColor Red
        Write-Host "       Action: Install or upgrade Node.js to v20.9.0 or higher." -ForegroundColor Yellow
        $hasFailure = $true
    }
} else {
    Write-Host "[FAIL] Node.js: Not found on PATH." -ForegroundColor Red
    Write-Host "       Action: Install Node.js (v20.9.0+ required by Next.js 16)." -ForegroundColor Yellow
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
# Check 7: Database configuration presence (non-blank check; no secrets printed)
# ------------------------------------------------------------------------------
$envDb = if ($PSBoundParameters.ContainsKey('OverrideDatabaseUrl')) { $OverrideDatabaseUrl } else { $env:DATABASE_URL }
$rEnv = if ($OverrideRootEnvPath) { $OverrideRootEnvPath } else { $rootEnvFile }
$bEnv = if ($OverrideBackendEnvPath) { $OverrideBackendEnvPath } else { $backendEnvFile }

$dbStatus = Get-DatabaseConfigStatus -envVal $envDb -rootEnvPath $rEnv -backendEnvPath $bEnv

if ($dbStatus.Configured) {
    Write-Host "[PASS] DATABASE_URL: Configured ($($dbStatus.Source))" -ForegroundColor Green
} else {
    Write-Host "[FAIL] DATABASE_URL: Not configured or blank." -ForegroundColor Red
    Write-Host "       Action: Set a non-blank `$env:DATABASE_URL in PowerShell session or configure in .env." -ForegroundColor Yellow
    Write-Host "       Reference: See .env.example or README.md for connection configuration instructions." -ForegroundColor Yellow
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

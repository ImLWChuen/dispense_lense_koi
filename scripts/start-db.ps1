# ==============================================================================
# scripts/start-db.ps1: Portable PostgreSQL Startup and Health Verification
# ==============================================================================
# Starts the persistent PostgreSQL 16 Compose service for DispenseIQ/DispenseLens
# without developer-specific paths, waiting for the health check to pass.
# ==============================================================================

[CmdletBinding()]
param()

$ErrorActionPreference = "Continue"

# 1. Resolve repository root from script location
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$composeFile = Join-Path $repoRoot "compose.yaml"

# 2. Verify Docker CLI availability on PATH
$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCmd) {
    Write-Host "[ERROR] Docker CLI was not found on PATH." -ForegroundColor Red
    Write-Host "Please install Docker Desktop and ensure 'docker.exe' is available in your PATH." -ForegroundColor Yellow
    exit 1
}

# 3. Verify Docker Engine availability and responsiveness
$dockerVersionOutput = (& docker version --format "{{.Server.Version}}" 2>&1) | Out-String
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker CLI is available, but the Docker engine is not running or accessible." -ForegroundColor Red
    Write-Host "Output: $dockerVersionOutput" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Action required:" -ForegroundColor Cyan
    Write-Host "Please launch Docker Desktop and wait until the Linux container engine is fully started." -ForegroundColor Cyan
    Write-Host "If the error mentions '//./pipe/dockerDesktopLinuxEngine', Docker Desktop is still booting or stopped." -ForegroundColor Cyan
    exit 1
}

# 4. Verify Compose configuration
if (-not (Test-Path $composeFile)) {
    Write-Host "[ERROR] Compose configuration file not found at: $composeFile" -ForegroundColor Red
    exit 1
}

$composeConfigOutput = (& docker compose -f "$composeFile" config 2>&1) | Out-String
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker Compose configuration in compose.yaml is invalid:" -ForegroundColor Red
    Write-Host "$composeConfigOutput" -ForegroundColor Yellow
    exit 1
}

# 5. Start only the PostgreSQL service
Write-Host "[INFO] Starting PostgreSQL service from compose.yaml..." -ForegroundColor Cyan
$composeUpOutput = (& docker compose -f "$composeFile" up -d postgres 2>&1) | Out-String
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker Compose failed to start the 'postgres' service:" -ForegroundColor Red
    Write-Host "$composeUpOutput" -ForegroundColor Yellow
    exit 1
}

# 6. Bounded wait for container to report healthy
$containerName = "dispenselens-postgres"
$maxWaitSeconds = 45
$pollIntervalSeconds = 2
$elapsed = 0

Write-Host "[INFO] Waiting for '$containerName' container to report healthy (timeout: ${maxWaitSeconds}s)..." -ForegroundColor Cyan
$isHealthy = $false

while ($elapsed -lt $maxWaitSeconds) {
    $inspectStatus = ((& docker inspect --format "{{.State.Health.Status}}" $containerName 2>$null) | Out-String).Trim()
    if ($inspectStatus -eq "healthy") {
        $isHealthy = $true
        break
    }

    $stateStatus = ((& docker inspect --format "{{.State.Status}}" $containerName 2>$null) | Out-String).Trim()
    if ($stateStatus -eq "exited" -or $stateStatus -eq "dead") {
        Write-Host "[ERROR] Container '$containerName' terminated unexpectedly (status: $stateStatus)." -ForegroundColor Red
        Write-Host "Inspect container logs with: docker logs $containerName" -ForegroundColor Yellow
        exit 1
    }

    Start-Sleep -Seconds $pollIntervalSeconds
    $elapsed += $pollIntervalSeconds
}

if (-not $isHealthy) {
    $currentStatus = ((& docker inspect --format "{{.State.Health.Status}}" $containerName 2>$null) | Out-String).Trim()
    Write-Host "[ERROR] Container '$containerName' failed to report healthy within ${maxWaitSeconds}s (status: '$currentStatus')." -ForegroundColor Red
    Write-Host "Inspect container logs with: docker logs $containerName" -ForegroundColor Yellow
    exit 1
}

Write-Host "[SUCCESS] PostgreSQL service is up and healthy." -ForegroundColor Green
Write-Host "Container: $containerName on port 5432"
Write-Host "Development volume 'postgres_data' preserved."
exit 0

# ==============================================================================
# scripts/verify-demo.ps1: Post-Start Application Identity and Health Verification
# ==============================================================================
# Read-only verification that checks:
# 1. Backend on http://127.0.0.1:8000/api/v1/health returns status="ok" and
#    service="dispense-lens-api".
# 2. Frontend on http://localhost:3001 responds with HTTP 200 and matches the
#    stable checked-in DispenseIQ / DispenseLens page identity.
#
# Returns exit code 0 on verified identity match, or exit code 1 on failure.
# ==============================================================================

[CmdletBinding()]
param(
    [string]$BackendUrl = "http://127.0.0.1:8000/api/v1/health",
    [string]$FrontendUrl = "http://localhost:3001",
    [int]$TimeoutSec = 5
)

$ErrorActionPreference = "Continue"

$hasFailure = $false

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " DispenseIQ Post-Start Identity Verification" -ForegroundColor Cyan
Write-Host " Backend Target:  $BackendUrl" -ForegroundColor Cyan
Write-Host " Frontend Target: $FrontendUrl" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ------------------------------------------------------------------------------
# 1. Verify Backend Identity (GET /api/v1/health)
# ------------------------------------------------------------------------------
Write-Host "[CHECK] Verifying FastAPI backend identity at $BackendUrl..." -ForegroundColor Cyan

try {
    $backendResponse = Invoke-RestMethod -Uri $BackendUrl -Method Get -TimeoutSec $TimeoutSec -ErrorAction Stop
    $statusVal = $backendResponse.status
    $serviceVal = $backendResponse.service
    $versionVal = $backendResponse.version

    if ($statusVal -eq "ok" -and $serviceVal -eq "dispense-lens-api") {
        Write-Host "[PASS] Backend Identity Verified:" -ForegroundColor Green
        Write-Host "       Service: $serviceVal"
        Write-Host "       Status:  $statusVal"
        Write-Host "       Version: $versionVal"
    } else {
        Write-Host "[FAIL] Backend Identity Mismatch: Service responded, but is NOT the DispenseLens API." -ForegroundColor Red
        Write-Host "       Expected service='dispense-lens-api', status='ok'." -ForegroundColor Yellow
        Write-Host "       Received service='$serviceVal', status='$statusVal'." -ForegroundColor Yellow
        Write-Host "       (Wrong local application detected at $BackendUrl)." -ForegroundColor Red
        $hasFailure = $true
    }
} catch {
    Write-Host "[FAIL] Backend Health Check Failed: Unable to reach $BackendUrl within ${TimeoutSec}s." -ForegroundColor Red
    Write-Host "       Error: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host "       Action: Start the backend server with: cd backend; .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000" -ForegroundColor Yellow
    $hasFailure = $true
}

Write-Host ""

# ------------------------------------------------------------------------------
# 2. Verify Frontend Identity (GET http://localhost:3001)
# ------------------------------------------------------------------------------
Write-Host "[CHECK] Verifying Next.js frontend identity at $FrontendUrl..." -ForegroundColor Cyan

try {
    $frontendResponse = Invoke-WebRequest -Uri $FrontendUrl -Method Get -TimeoutSec $TimeoutSec -UseBasicParsing -ErrorAction Stop
    $statusCode = $frontendResponse.StatusCode
    $content = $frontendResponse.Content

    if ($statusCode -eq 200) {
        $hasIdentityMatch = ($content -like "*<title>DispenseLens</title>*") -or
                            ($content -like "*DispenseLens*") -or
                            ($content -like "*DispenseIQ*")

        if ($hasIdentityMatch) {
            Write-Host "[PASS] Frontend Identity Verified: Responding at $FrontendUrl (HTTP $statusCode)" -ForegroundColor Green
            Write-Host "       Page identity: Matches DispenseLens / DispenseIQ application."
        } else {
            Write-Host "[FAIL] Frontend Identity Mismatch: Service responded at $FrontendUrl with HTTP 200, but is NOT DispenseIQ." -ForegroundColor Red
            Write-Host "       Expected document title or content containing 'DispenseLens' or 'DispenseIQ'." -ForegroundColor Yellow
            Write-Host "       (Wrong local application detected at $FrontendUrl)." -ForegroundColor Red
            $hasFailure = $true
        }
    } else {
        Write-Host "[FAIL] Frontend responded with unexpected HTTP status $statusCode (expected 200)." -ForegroundColor Red
        $hasFailure = $true
    }
} catch {
    Write-Host "[FAIL] Frontend Verification Failed: Unable to reach $FrontendUrl within ${TimeoutSec}s." -ForegroundColor Red
    Write-Host "       Error: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host "       Action: Start the frontend server with: cd frontend; npm run dev -- -p 3001" -ForegroundColor Yellow
    Write-Host "       Note: Do not use port 3000, which may be occupied by an unrelated local service." -ForegroundColor Yellow
    $hasFailure = $true
}

# ------------------------------------------------------------------------------
# Summary and Outcome
# ------------------------------------------------------------------------------
Write-Host ""
if ($hasFailure) {
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host " VERIFICATION FAILED: One or more demo services failed check." -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
    exit 1
} else {
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host " VERIFICATION SUCCESSFUL: DispenseIQ services are verified!" -ForegroundColor Green
    Write-Host " Ready for demonstration at: $FrontendUrl" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    exit 0
}

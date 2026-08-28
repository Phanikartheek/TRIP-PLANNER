Set-Location -Path $PSScriptRoot
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host " Starting AI Trip Planner (Frontend + Backend)..." -ForegroundColor Green
Write-Host "====================================================" -ForegroundColor Cyan

if (Test-Path ".venv\Scripts\python.exe") {
    & .venv\Scripts\python.exe run.py
} else {
    python run.py
}

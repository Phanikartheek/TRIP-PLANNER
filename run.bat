@echo off
title AI Trip Planner
cd /d "%~dp0"
echo ====================================================
echo  Starting AI Trip Planner (Frontend + Backend)...
echo ====================================================

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run.py
) else (
    python run.py
)

if %ERRORLEVEL% neq 0 (
    echo.
    echo Server stopped with error.
    pause
)

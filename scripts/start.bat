@echo off
REM Startup script for Document Search Application (Windows)

echo Document Search Application Startup
echo ====================================

REM Check if .env file exists
if not exist ".env" (
    echo Error: .env file not found. Please run setup first:
    echo   python scripts/setup.py
    exit /b 1
)

REM Check if virtual environment exists
if not exist "venv" (
    echo Error: Virtual environment not found. Please run setup first:
    echo   python scripts/setup.py
    exit /b 1
)

echo Starting services...

REM Start Elasticsearch in background
echo Starting Elasticsearch...
docker-compose up elasticsearch -d

REM Wait for Elasticsearch to be ready
echo Waiting for Elasticsearch to be ready...
set max_attempts=30
set attempt=0

:wait_loop
if %attempt% geq %max_attempts% (
    echo Error: Elasticsearch failed to start
    exit /b 1
)

powershell -Command "try { Invoke-RestMethod -Uri http://localhost:9200/_cluster/health -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if %errorlevel% equ 0 (
    echo ✓ Elasticsearch is ready
    goto elasticsearch_ready
)

set /a attempt+=1
echo   Waiting for Elasticsearch... (%attempt%/%max_attempts%)
timeout /t 2 /nobreak >nul
goto wait_loop

:elasticsearch_ready
REM Activate virtual environment and start API
echo Starting Document Search FastAPI...
call venv\Scripts\activate
set PYTHONPATH=%cd%\src

REM Start the FastAPI application with uvicorn
uvicorn src.api.app:app --host 0.0.0.0 --port 5000 --reload 
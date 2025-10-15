@echo off
echo ==========================================
echo Stopping Container
echo ==========================================
echo.

cd /d "%~dp0"

docker-compose stop

if %errorLevel% neq 0 (
    echo [ERROR] Failed to stop container
    pause
    exit /b 1
)

echo.
echo Container stopped successfully.
echo.

pause

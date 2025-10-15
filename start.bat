@echo off
echo ==========================================
echo Starting Container
echo ==========================================
echo.

cd /d "%~dp0"

docker-compose up -d

if %errorLevel% neq 0 (
    echo [ERROR] Failed to start container
    pause
    exit /b 1
)

echo.
echo Container status:
docker-compose ps

echo.
echo Recent logs:
docker-compose logs --tail=10

echo.
echo Application URL: http://localhost:5000
echo.

pause

@echo off
echo ==========================================
echo Restarting Container
echo ==========================================
echo.

cd /d "%~dp0"

docker-compose restart

if %errorLevel% neq 0 (
    echo [ERROR] Failed to restart container
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
echo Restart completed!
echo.

pause

@echo off
echo ==========================================
echo System Status Check
echo ==========================================
echo.

cd /d "%~dp0"

echo [Container Status]
docker-compose ps
echo.

echo [Recent Logs - 20 lines]
docker-compose logs --tail=20
echo.

echo [Health Check]
curl -s http://localhost:5000/health
echo.
echo.

echo [API Status]
curl -s http://localhost:5000/api/status
echo.
echo.

echo [System Monitoring]
curl -s http://localhost:5000/api/monitor
echo.
echo.

pause

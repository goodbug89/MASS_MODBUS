@echo off
echo ==========================================
echo View Real-time Logs
echo ==========================================
echo.
echo Press Ctrl+C to exit.
echo.

cd /d "%~dp0"

docker-compose logs -f

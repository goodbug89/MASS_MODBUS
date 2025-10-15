@echo off
echo ==========================================
echo Clean All (Complete Cleanup)
echo ==========================================
echo.
echo [WARNING] This will perform the following:
echo  - Stop and remove all containers
echo  - Remove all images
echo  - Remove all volumes
echo  - Remove all networks
echo.

set /p confirm="Continue? (Y/N): "
if /i not "%confirm%"=="Y" (
    echo Operation cancelled.
    pause
    exit /b 0
)

cd /d "%~dp0"

echo.
echo [1/4] Stopping and removing containers...
docker-compose down -v
echo.

echo [2/4] Removing images...
docker-compose down --rmi all
echo.

echo [3/4] Cleaning up unused Docker resources...
docker system prune -af --volumes
echo.

echo [4/4] Cleanup completed!
echo.
echo All Docker resources have been removed.
echo Run deploy.bat to start again.
echo.

pause

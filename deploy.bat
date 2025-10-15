@echo off
echo ==========================================
echo CIE-H14A Modbus Controller Deployment
echo ==========================================
echo.

:: Check admin privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [WARNING] Administrator privileges may be required.
    echo.
)

:: Check current directory
echo [1/7] Checking working directory...
cd /d "%~dp0"
echo Current location: %CD%
echo.

:: Check Docker
echo [2/7] Checking Docker status...
docker --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Docker is not installed or not running.
    echo Please install and run Docker Desktop.
    pause
    exit /b 1
)
echo Docker check completed
echo.

:: Stop and remove existing containers
echo [3/7] Stopping and removing existing containers...
docker-compose down
if %errorLevel% neq 0 (
    echo [WARNING] Error stopping containers (continuing anyway)
)
echo.

:: Clean up old images
echo [4/7] Cleaning up old Docker images...
docker image prune -f
echo.

:: Build Docker image
echo [5/7] Building Docker image...
echo This may take a few minutes.
docker-compose build --no-cache
if %errorLevel% neq 0 (
    echo [ERROR] Docker image build failed
    pause
    exit /b 1
)
echo Build completed
echo.

:: Start container
echo [6/7] Starting container...
docker-compose up -d
if %errorLevel% neq 0 (
    echo [ERROR] Container start failed
    pause
    exit /b 1
)
echo Container started successfully
echo.

:: Check status
echo [7/7] Checking deployment status...
timeout /t 3 /nobreak >nul
docker-compose ps
echo.

:: View logs
echo ==========================================
echo Recent logs (10 lines):
echo ==========================================
docker-compose logs --tail=10
echo.

:: Health Check
echo ==========================================
echo Performing Health Check...
echo ==========================================
timeout /t 2 /nobreak >nul
curl -s http://localhost:5000/health
echo.
echo.

:: Completion message
echo ==========================================
echo Deployment Complete!
echo ==========================================
echo.
echo Application URL: http://localhost:5000
echo API Status: http://localhost:5000/api/status
echo Health Check: http://localhost:5000/health
echo Monitoring: http://localhost:5000/api/monitor
echo.
echo View real-time logs: docker-compose logs -f
echo Stop container: docker-compose stop
echo Restart container: docker-compose restart
echo.

pause

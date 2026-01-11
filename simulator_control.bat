@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ======================================
echo  Modbus 시뮬레이터 제어
echo ======================================
echo.

:menu
echo [1] 시뮬레이터 시작 (Start)
echo [2] 시뮬레이터 중지 (Stop)
echo [3] 시뮬레이터 재시작 (Restart)
echo [4] 시뮬레이터 상태 확인 (Status)
echo [5] 시뮬레이터 로그 보기 (Logs)
echo [0] 종료 (Exit)
echo.
set /p choice="선택하세요 (0-5): "

if "%choice%"=="1" goto start
if "%choice%"=="2" goto stop
if "%choice%"=="3" goto restart
if "%choice%"=="4" goto status
if "%choice%"=="5" goto logs
if "%choice%"=="0" goto end
echo 잘못된 선택입니다.
echo.
goto menu

:start
echo.
echo [시뮬레이터 시작 중...]
docker-compose up -d modbus-simulator
echo.
echo 시뮬레이터가 시작되었습니다.
timeout /t 3 >nul
echo.
goto menu

:stop
echo.
echo [시뮬레이터 중지 중...]
docker-compose stop modbus-simulator
echo.
echo 시뮬레이터가 중지되었습니다.
timeout /t 2 >nul
echo.
goto menu

:restart
echo.
echo [시뮬레이터 재시작 중...]
docker-compose restart modbus-simulator
echo.
echo 시뮬레이터가 재시작되었습니다.
timeout /t 3 >nul
echo.
goto menu

:status
echo.
echo [시뮬레이터 상태 확인]
echo.
docker-compose ps modbus-simulator
echo.
pause
echo.
goto menu

:logs
echo.
echo [시뮬레이터 로그 (Ctrl+C로 종료)]
echo.
docker-compose logs -f modbus-simulator
echo.
goto menu

:end
echo.
echo 프로그램을 종료합니다.
timeout /t 1 >nul
exit /b 0

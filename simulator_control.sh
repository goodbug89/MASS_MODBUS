#!/bin/bash

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "======================================"
echo " Modbus 시뮬레이터 제어"
echo "======================================"
echo ""

show_menu() {
    echo -e "${BLUE}[1]${NC} 시뮬레이터 시작 (Start)"
    echo -e "${BLUE}[2]${NC} 시뮬레이터 중지 (Stop)"
    echo -e "${BLUE}[3]${NC} 시뮬레이터 재시작 (Restart)"
    echo -e "${BLUE}[4]${NC} 시뮬레이터 상태 확인 (Status)"
    echo -e "${BLUE}[5]${NC} 시뮬레이터 로그 보기 (Logs)"
    echo -e "${BLUE}[0]${NC} 종료 (Exit)"
    echo ""
}

start_simulator() {
    echo ""
    echo -e "${GREEN}[시뮬레이터 시작 중...]${NC}"
    docker-compose up -d modbus-simulator
    echo ""
    echo -e "${GREEN}시뮬레이터가 시작되었습니다.${NC}"
    sleep 2
}

stop_simulator() {
    echo ""
    echo -e "${YELLOW}[시뮬레이터 중지 중...]${NC}"
    docker-compose stop modbus-simulator
    echo ""
    echo -e "${YELLOW}시뮬레이터가 중지되었습니다.${NC}"
    sleep 2
}

restart_simulator() {
    echo ""
    echo -e "${YELLOW}[시뮬레이터 재시작 중...]${NC}"
    docker-compose restart modbus-simulator
    echo ""
    echo -e "${GREEN}시뮬레이터가 재시작되었습니다.${NC}"
    sleep 2
}

show_status() {
    echo ""
    echo -e "${BLUE}[시뮬레이터 상태 확인]${NC}"
    echo ""
    docker-compose ps modbus-simulator
    echo ""
    read -p "계속하려면 Enter를 누르세요..."
}

show_logs() {
    echo ""
    echo -e "${BLUE}[시뮬레이터 로그 (Ctrl+C로 종료)]${NC}"
    echo ""
    docker-compose logs -f modbus-simulator
}

while true; do
    show_menu
    read -p "선택하세요 (0-5): " choice

    case $choice in
        1)
            start_simulator
            ;;
        2)
            stop_simulator
            ;;
        3)
            restart_simulator
            ;;
        4)
            show_status
            ;;
        5)
            show_logs
            ;;
        0)
            echo ""
            echo -e "${GREEN}프로그램을 종료합니다.${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}잘못된 선택입니다.${NC}"
            sleep 1
            ;;
    esac

    echo ""
done

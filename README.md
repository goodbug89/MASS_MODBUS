# CIE-H14A Modbus TCP/IP 멀티 제어 시스템

<p align="center">
  <img src="https://img.shields.io/badge/Version-2.2.0-orange.svg" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/Flask-3.0-green.svg" alt="Flask">
  <img src="https://img.shields.io/badge/Docker-Ready-blue.svg" alt="Docker">
  <img src="https://img.shields.io/badge/Multi--Device-8-brightgreen.svg" alt="Multi-Device">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

**최대 8대**의 CIE-H14A 4채널 원격 I/O 컨트롤러를 Modbus TCP/IP 프로토콜을 통해 웹에서 동시에 모니터링하고 제어하는 시스템입니다.

> 📚 **상세 문서**: [MANUAL.md](MANUAL.md) - API 레퍼런스, 환경 설정, 문제 해결 가이드

## 주요 기능

- 🚀 **멀티 디바이스 지원**: 최대 8대 장비 동시 제어
- 🔌 **4채널 디지털 입력 모니터링**: 실시간 입력 상태 표시 (각 장비당 4채널)
- ⚡ **4채널 디지털 출력 제어**: 웹 인터페이스를 통한 릴레이 제어 (각 장비당 4채널)
- 🔄 **실시간 업데이트**: Server-Sent Events를 통한 자동 상태 갱신 (25ms 주기)
- 📡 **외부 서버 연동**: DI 상태 변화 시 HTTP GET 요청 자동 전송 (개별 채널별)
- ⏱️ **자동 DO 제어**: DI0-DI2 시간차 기반 DO3 자동 펄스 제어
- 🔄 **출력 자동 꺼짐**: duration 파라미터로 출력 ON 후 자동 OFF (ms 단위)
- 🎨 **Glass Morphism UI**: 다크모드 + 반투명 유리 효과 디자인
- 📱 **반응형 디자인**: 모바일, 태블릿, 데스크톱 지원
- 🐳 **Docker 지원**: 간편한 배포 및 실행
- 🔧 **자동 재연결**: 각 장비별 독립적인 자동 재연결
- 📊 **통합 모니터링**: 모든 장비의 상태를 한 화면에서 확인
- 🔒 **보안 강화**: OWASP 기반 입력 검증 및 XSS 방지
- 🚴 **UWB 하이패스 시스템**: 이륜차 입출차 자동 감지 및 신호등 제어

## 빠른 시작

### 사전 요구사항

- Docker & Docker Compose (권장)
- 또는 Python 3.11+ (로컬 개발 시)
- CIE-H14A 제어기 (네트워크 연결)

### Docker로 실행 (권장)

1. **환경 설정**
   ```bash
   cp .env.example .env
   # .env 파일을 편집하여 각 장비의 IP 주소 설정
   ```

   최소 설정 예시 (4대 장비):
   ```env
   DEVICE1_ENABLED=true
   DEVICE1_NAME=Lane1
   DEVICE1_HOST=192.168.10.101

   DEVICE2_ENABLED=true
   DEVICE2_NAME=Lane2
   DEVICE2_HOST=192.168.10.102

   DEVICE3_ENABLED=true
   DEVICE3_NAME=Lane3
   DEVICE3_HOST=192.168.10.103

   DEVICE4_ENABLED=true
   DEVICE4_NAME=Lane4
   DEVICE4_HOST=192.168.10.104
   ```

2. **실행**
   ```bash
   docker-compose up -d
   ```

3. **접속**

   브라우저에서 `http://localhost:5000` 접속

4. **로그 확인**
   ```bash
   docker-compose logs -f
   ```

### 시뮬레이터 제어

내장된 Modbus 시뮬레이터를 ON/OFF 할 수 있습니다:

**Windows:**

```bash
simulator_control.bat
```

**Linux/Mac:**

```bash
./simulator_control.sh
```

**메뉴 옵션:**

- [1] 시뮬레이터 시작
- [2] 시뮬레이터 중지
- [3] 시뮬레이터 재시작
- [4] 시뮬레이터 상태 확인
- [5] 시뮬레이터 로그 보기

**명령줄에서 직접 제어:**

```bash
# 시뮬레이터만 시작
docker-compose up -d modbus-simulator

# 시뮬레이터만 중지
docker-compose stop modbus-simulator

# 시뮬레이터만 재시작
docker-compose restart modbus-simulator

# 시뮬레이터 상태 확인
docker-compose ps modbus-simulator
```

**웹 대시보드에서 제어:**

`http://localhost:5000` 접속 후 상단의 "Modbus 시뮬레이터 제어" 카드에서 버튼 클릭으로 제어 가능합니다.

### 로컬에서 실행

1. **가상환경 생성 및 활성화**
   ```bash
   python -m venv venv

   # Windows
   venv\Scripts\activate

   # Linux/Mac
   source venv/bin/activate
   ```

2. **의존성 설치**
   ```bash
   pip install -r requirements.txt
   ```

3. **환경 설정**
   ```bash
   cp .env.example .env
   # .env 파일 편집
   ```

4. **실행**
   ```bash
   python run.py
   ```

## 환경 변수 설정

### 전역 기본값 설정

`.env` 파일에서 모든 장비에 공통으로 적용되는 기본값을 설정합니다:

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `MODBUS_DEFAULT_PORT` | Modbus TCP 포트 | 502 |
| `MODBUS_DEFAULT_UNIT_ID` | Modbus Unit ID | 1 |
| `MODBUS_DEFAULT_TIMEOUT` | 연결 타임아웃 (초) | 0.3 |
| `MODBUS_DEFAULT_POLL_INTERVAL` | DI 폴링 간격 (초) | **0.025** (25ms, 고속 감지) |
| `MODBUS_DEFAULT_AUTO_OFF_TIME` | 자동 OFF 시간 (초) | 1.0 |
| `MODBUS_DEFAULT_RETRY_COUNT` | 재시도 횟수 | 3 |
| `MODBUS_DEFAULT_RETRY_DELAY` | 재시도 간격 (초) | 0.1 |
| `SENSOR_URL` | DI 감지 시 호출할 센서 URL (공통) | http://localhost:5000/api/get_sensor |
| `FLASK_ENV` | Flask 환경 | production |
| `SECRET_KEY` | Flask 시크릿 키 | (변경 필수) |

### 장비별 설정

각 장비(DEVICE1-8)마다 개별 설정이 가능합니다:

| 변수 패턴 | 설명 | 필수 여부 |
|----------|------|-----------|
| `DEVICE{N}_ENABLED` | 장비 활성화 여부 (true/false) | **필수** |
| `DEVICE{N}_NAME` | 장비 이름 (예: Lane1) | **필수** |
| `DEVICE{N}_HOST` | 장비 IP 주소 | **필수** |
| `DEVICE{N}_PORT` | 개별 포트 (기본값 사용 시 생략 가능) | 선택 |
| `DEVICE{N}_UNIT_ID` | 개별 Unit ID (기본값 사용 시 생략 가능) | 선택 |
| `DEVICE{N}_TIMEOUT` | 개별 타임아웃 (기본값 사용 시 생략 가능) | 선택 |
| `DEVICE{N}_POLL_INTERVAL` | 개별 폴링 간격 (기본값 사용 시 생략 가능) | 선택 |
| `DEVICE{N}_SENSOR_URL` | 개별 센서 URL (공통 URL 사용 시 생략 가능) | 선택 |

### UWB 하이패스 시스템 설정

이륜차 입출차 자동 감지 시스템의 센서 및 신호등 매핑을 .env에서 설정할 수 있습니다:

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `HIPASS_LANE1_SENSOR1_DI` | Lane 1 외부측 레이저 센서 (DI 채널) | 1 |
| `HIPASS_LANE1_SENSOR2_DI` | Lane 1 내부측 레이저 센서 (DI 채널) | 3 |
| `HIPASS_LANE2_SENSOR1_DI` | Lane 2 외부측 레이저 센서 (DI 채널) | 0 |
| `HIPASS_LANE2_SENSOR2_DI` | Lane 2 내부측 레이저 센서 (DI 채널) | 2 |
| `HIPASS_LANE1_GREEN_DO` | Lane 1 초록 신호등 (DO 채널) | 0 |
| `HIPASS_LANE1_RED_DO` | Lane 1 빨강 신호등 (DO 채널) | 1 |
| `HIPASS_LANE2_GREEN_DO` | Lane 2 초록 신호등 (DO 채널) | 2 |
| `HIPASS_LANE2_RED_DO` | Lane 2 빨강 신호등 (DO 채널) | 3 |
| `HIPASS_INVERT_SENSOR_LOGIC` | 센서 로직 반전 (NC 타입 센서용) | false |

**설정 예시**:

```env
# 전역 기본값
MODBUS_DEFAULT_PORT=502
MODBUS_DEFAULT_UNIT_ID=1
SENSOR_URL=http://localhost:5000/api/get_sensor

# 장비 1 (최소 설정 - 기본값 사용)
DEVICE1_ENABLED=true
DEVICE1_NAME=Lane1
DEVICE1_HOST=192.168.10.101

# 장비 2 (개별 포트 설정)
DEVICE2_ENABLED=true
DEVICE2_NAME=Lane2
DEVICE2_HOST=192.168.10.102
DEVICE2_PORT=5020

# 장비 3-4 (최소 설정)
DEVICE3_ENABLED=true
DEVICE3_NAME=Lane3
DEVICE3_HOST=192.168.10.103

DEVICE4_ENABLED=true
DEVICE4_NAME=Lane4
DEVICE4_HOST=192.168.10.104
```

## 프로젝트 구조

```
MASS_MODBUS/
├── app/
│   ├── __init__.py              # Flask 앱 초기화
│   ├── modbus_client.py         # Modbus TCP 클라이언트
│   ├── routes.py                # API 라우트
│   └── static/
│       ├── css/
│       │   └── style.css        # 스타일시트
│       ├── js/
│       │   └── main.js          # 프론트엔드 로직
│       └── index.html           # 메인 HTML
├── config/
│   ├── __init__.py
│   └── config.py                # 설정 파일
├── tests/
│   ├── __init__.py
│   ├── test_modbus_client.py   # Modbus 클라이언트 테스트
│   └── test_routes.py           # API 라우트 테스트
├── .env.example                 # 환경 변수 템플릿
├── .gitignore                   # Git 제외 파일
├── .dockerignore                # Docker 제외 파일
├── CLAUDE.md                    # Claude Code 가이드
├── Dockerfile                   # Docker 이미지 정의
├── docker-compose.yml           # Docker Compose 설정
├── requirements.txt             # Python 의존성
├── run.py                       # 서버 실행 스크립트
└── README.md                    # 이 파일
```

## API 문서

### 멀티 디바이스 API 엔드포인트

#### 📊 상태 조회 및 모니터링

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/` | GET | 메인 웹 페이지 |
| `/health` | GET | 헬스 체크 (전체 장비 연결 상태) |
| `/api/status` | GET | **모든 장비** 상태 조회 |
| `/api/devices` | GET | 장비 목록 조회 |
| `/api/devices/<device_id>/status` | GET | 특정 장비 상태 조회 |
| `/api/events` | GET | **모든 장비** SSE 실시간 스트림 |
| `/api/config` | GET | 현재 설정 조회 |
| `/api/monitor` | GET | API 모니터링 정보 조회 |

#### ⚡ 출력 제어 (POST 방식)

| 엔드포인트 | 메서드 | 설명 | Body |
|-----------|--------|------|------|
| `/api/devices/<device_id>/output/<channel>` | POST | 특정 장비 출력 ON/OFF | `{"state": true/false}` |
| `/api/devices/<device_id>/output/<channel>/toggle` | POST | 특정 장비 출력 토글 | (없음) |

#### 🌐 출력 제어 (GET 방식 - 웹 브라우저 직접 제어)

| 엔드포인트 | 메서드 | 설명 | 사용 예시 |
|-----------|--------|------|----------|
| `/api/devices/<device_id>/output/<channel>/on` | GET | 출력 켜기 | `/api/devices/device1/output/0/on` |
| `/api/devices/<device_id>/output/<channel>/off` | GET | 출력 끄기 | `/api/devices/device1/output/0/off` |
| `/api/devices/<device_id>/output/<channel>/set?state=<value>` | GET | 파라미터로 제어 | `/api/devices/device1/output/0/set?state=on` |

**GET 방식 state 파라미터**: `on`, `off`, `1`, `0`, `true`, `false`

#### 📡 센서 엔드포인트 (DI 감지 시 자동 호출)

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/get_sensor?id=<device_id>&di_states=<states>&time=<ms>` | GET | DI 감지 수신 |

### 하위 호환 API (레거시)

기존 단일 장비 API도 계속 지원됩니다 (첫 번째 장비로 자동 라우팅):

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/output/<channel>` | POST | 첫 번째 장비 출력 제어 |
| `/api/output/<channel>/toggle` | POST | 첫 번째 장비 출력 토글 |

### 사용 예시

**모든 장비 상태 조회**
```bash
curl http://localhost:5000/api/status
```

응답:
```json
{
  "devices": {
    "device1": {
      "name": "Lane1",
      "host": "192.168.10.101",
      "connected": true,
      "inputs": [false, true, false, true],
      "outputs": [true, false, false, true],
      "timestamp": 1697186400.123
    },
    "device2": {
      "name": "Lane2",
      "host": "192.168.10.102",
      "connected": true,
      "inputs": [true, false, false, false],
      "outputs": [false, true, false, true],
      "timestamp": 1697186400.456
    }
  }
}
```

**특정 장비 출력 제어 (POST)**
```bash
# DO0 켜기
curl -X POST http://localhost:5000/api/devices/device1/output/0 \
  -H "Content-Type: application/json" \
  -d '{"state": true}'

# DO0 끄기
curl -X POST http://localhost:5000/api/devices/device1/output/0 \
  -H "Content-Type: application/json" \
  -d '{"state": false}'
```

**특정 장비 출력 제어 (GET - 웹 브라우저)**
```bash
# 방법 1: /on, /off 엔드포인트
curl http://localhost:5000/api/devices/device1/output/0/on
curl http://localhost:5000/api/devices/device1/output/0/off

# 방법 2: /set 엔드포인트 (파라미터 사용)
curl http://localhost:5000/api/devices/device1/output/0/set?state=on
curl http://localhost:5000/api/devices/device1/output/0/set?state=off
curl http://localhost:5000/api/devices/device1/output/0/set?state=1
curl http://localhost:5000/api/devices/device1/output/0/set?state=0

# 웹 브라우저 주소창에 직접 입력 가능:
# http://localhost:5000/api/devices/device2/output/1/on
```

**특정 장비 출력 토글**
```bash
curl -X POST http://localhost:5000/api/devices/device2/output/3/toggle
```

**SSE 스트림 (모든 장비 실시간 업데이트)**
```bash
curl http://localhost:5000/api/events
```

응답:
```
data: {"type":"initial","devices":{"device1":{...},"device2":{...}}}

data: {"type":"update","devices":{"device1":{"inputs":[true,false,false,false]}}}
```

## 개발

### 테스트 실행

```bash
# 단위 테스트
pytest

# 커버리지 포함
pytest --cov=app tests/
```

### Docker 개발

```bash
# 이미지 빌드 및 실행
docker-compose up --build

# 로그 확인
docker-compose logs -f

# 중지
docker-compose down
```

## Modbus 레지스터 매핑

CIE-H14A 하드웨어 사양:

| 채널 | 타입 | Function Code | 주소 | 비고 |
|------|------|---------------|------|------|
| DI0-DI3 | 입력 | FC 02 (Read Discrete Inputs) | 0-3 | 디지털 입력 |
| DO0-DO3 | 출력 | FC 05 (Write Single Coil) | 8-11 | 릴레이 출력 |

**중요**: 출력 주소는 0이 아닌 8부터 시작합니다!

## 기술 스택

- **Backend**: Python 3.11, Flask 3.0
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5
- **Protocol**: Modbus TCP/IP (pyModbusTCP)
- **Containerization**: Docker, Docker Compose
- **Real-time**: Server-Sent Events (SSE)
- **WSGI Server**: Gunicorn

## 멀티 디바이스 아키텍처

### 핵심 설계

- **독립적인 연결 관리**: 각 장비는 독립적인 Modbus 클라이언트 인스턴스를 가짐
- **독립적인 폴링**: 각 장비마다 별도의 백그라운드 폴링 스레드 실행
- **독립적인 상태 관리**: 한 장비의 연결 실패가 다른 장비에 영향 없음
- **통합 모니터링**: 웹 UI에서 모든 장비를 한 화면에서 관리
- **효율적인 SSE**: 변경된 장비의 상태만 전송 (대역폭 최적화)

### 확장성

- 현재: 최대 8대까지 지원
- 필요 시 `config/config.py`에서 `range(1, 9)`를 수정하여 더 많은 장비 지원 가능
- 각 장비는 별도 IP 주소 또는 별도 포트 사용 가능

## 트러블슈팅

### Modbus 연결 실패

**문제**: 특정 장비 연결 실패 `[device1] Modbus 연결 실패: 192.168.10.101:502`

**해결**:
1. 해당 장비의 전원 및 네트워크 연결 확인
2. IP 주소 핑 테스트: `ping 192.168.10.101`
3. 방화벽 포트 502 개방 확인
4. CIE-H14A에서 Modbus TCP 활성화 확인 (ezManager 도구 사용)
5. `.env` 파일에서 해당 장비의 `DEVICE{N}_ENABLED=true` 확인

**참고**: 한 장비의 연결 실패가 다른 장비에는 영향을 주지 않습니다.

### 일부 장비만 표시됨

**문제**: 웹 UI에서 일부 장비만 보임

**해결**:
1. `.env` 파일에서 `DEVICE{N}_ENABLED=true` 확인
2. `DEVICE{N}_HOST`가 올바르게 설정되었는지 확인
3. 서버 재시작: `docker-compose restart`
4. 로그 확인: `docker-compose logs -f`

### Docker 네트워크 이슈

**문제**: 컨테이너에서 호스트 네트워크의 장비 접근 불가

**해결**: `docker-compose.yml`에서 `network_mode: host` 사용

### 포트 충돌

**문제**: `Address already in use: 5000`

**해결**:
```bash
# Windows
netstat -ano | findstr :5000

# Linux/Mac
lsof -i :5000

# 프로세스 종료 후 다시 실행
```

### 시뮬레이터로 테스트

**로컬 시뮬레이터 사용 시**:

```env
# 각 장비마다 다른 포트 사용
DEVICE1_HOST=127.0.0.1
DEVICE1_PORT=5020

DEVICE2_HOST=127.0.0.1
DEVICE2_PORT=5021

DEVICE3_HOST=127.0.0.1
DEVICE3_PORT=5022

DEVICE4_HOST=127.0.0.1
DEVICE4_PORT=5023
```

시뮬레이터 실행:
```bash
# tests/modbus_simulator.py 사용
python tests/modbus_simulator.py
```

## Claude Code 활용

이 프로젝트는 Claude Code와 함께 사용하도록 최적화되어 있습니다.

```bash
# 새 기능 추가
claude-code "app/routes.py에 입력 히스토리 API를 추가해줘"

# 버그 수정
claude-code "재연결 로직 개선해줘"

# 테스트 작성
claude-code "modbus_client.py에 대한 단위 테스트 작성해줘"
```

자세한 내용은 [CLAUDE.md](CLAUDE.md) 참조

## 성능 및 최적화

### 25ms 고속 폴링 성능

**폴링 주기 설정:**
```env
MODBUS_DEFAULT_POLL_INTERVAL=0.025  # 25ms (기본값)
```

#### 성능 지표

| 항목 | 값 | 설명 |
|------|-----|------|
| **폴링 주기** | 25ms | 초당 40회 DI 상태 체크 |
| **응답 시간** | ~30-50ms | DI 감지부터 UI 업데이트까지 |
| **CPU 사용률** | 5-15% | 8대 장비 기준 (Intel i5 이상) |
| **메모리 사용량** | ~512MB | 8대 장비 기준 |
| **네트워크 대역폭** | ~10KB/s | 장비당 (총 ~80KB/s for 8 devices) |

#### 장비 수별 리소스 사용량

| 장비 수 | CPU (평균) | 메모리 | 초당 요청 수 | 권장 하드웨어 |
|---------|------------|--------|--------------|--------------|
| 1-2대 | 2-5% | 256MB | 80 req/s | Raspberry Pi 4 |
| 3-4대 | 5-10% | 512MB | 160 req/s | 일반 PC/서버 |
| 5-8대 | 10-15% | 1GB | 320 req/s | 서버급 CPU 권장 |

#### 폴링 주기 선택 가이드

**차량 속도에 따른 권장 폴링 주기:**

| 차량 속도 | 센서 간격 | 권장 폴링 | 이동 거리/폴링 | 놓칠 위험 |
|-----------|-----------|-----------|----------------|-----------|
| 20 km/h | 1m | 50ms | ~0.28m | 낮음 |
| 50 km/h | 1m | **25ms** ⭐ | ~0.35m | 매우 낮음 |
| 100 km/h | 1m | 10ms | ~0.28m | 낮음 |

**⭐ 권장: 25ms** - 성능과 정확도의 최적 균형

#### 폴링 주기 튜닝

**용도별 권장 설정:**

```env
# 초고속 감지 (고속도로 출입구)
MODBUS_DEFAULT_POLL_INTERVAL=0.01  # 10ms

# 일반 출입 관리 (권장) ⭐
MODBUS_DEFAULT_POLL_INTERVAL=0.025  # 25ms

# 저속 모니터링 (주차장)
MODBUS_DEFAULT_POLL_INTERVAL=0.05  # 50ms

# 단순 상태 체크 (에너지 절약)
MODBUS_DEFAULT_POLL_INTERVAL=0.1  # 100ms
```

#### 네트워크 요구사항

**권장 네트워크 환경:**
- 최소 대역폭: 100Mbps (8대 장비 기준)
- 권장: 1Gbps Ethernet
- Modbus 장비와 동일 네트워크 세그먼트 배치 권장
- 최대 거리: 100m (Cat5e/Cat6 기준)

### 최적화 팁

1. **장비 수 제한**: 실제 필요한 장비만 활성화 (`DEVICEN_ENABLED=true`)
2. **폴링 주기 조정**: 용도에 맞게 적절한 값 설정
3. **네트워크 분리**: Modbus 전용 VLAN 사용 권장
4. **로그 레벨**: 프로덕션에서는 `LOG_LEVEL=INFO` 사용 (DEBUG는 성능 저하)
5. **SSE 연결 수**: 불필요한 브라우저 탭 닫기 (연결당 ~2MB 메모리)

## 보안 고려사항

### ⚠️ Docker 소켓 마운팅 보안 위험

**중요**: 시뮬레이터 제어 기능을 사용하기 위해 Docker 소켓(`/var/run/docker.sock`)을 컨테이너에 마운트합니다. 이는 다음과 같은 **보안 위험**을 포함합니다:

#### 위험 요소
- **호스트 루트 권한**: Docker 소켓 접근 권한은 호스트 시스템에 대한 루트 권한과 동등합니다
- **컨테이너 탈출**: 공격자가 Flask 앱을 해킹하면 다른 모든 컨테이너를 제어하고 호스트로 탈출할 수 있습니다
- **데이터 유출**: 호스트의 모든 볼륨과 데이터에 접근 가능합니다

#### 권장 보안 조치

**프로덕션 환경에서 필수:**

1. **API 인증 활성화**
   ```env
   # .env 파일
   SIMULATOR_API_KEY=강력한-랜덤-키-생성-필요
   ```

2. **네트워크 분리**
   - 시뮬레이터 제어 API는 신뢰할 수 있는 네트워크에서만 접근 가능하도록 설정
   - 방화벽 규칙으로 IP 화이트리스트 적용

3. **대안 고려**
   - **개발/테스트 전용**: Docker 소켓 마운팅은 개발 환경에서만 사용
   - **프로덕션 대안**: Docker API를 별도 인증 레이어를 통해 사용하거나, 시뮬레이터 제어 기능 비활성화

4. **모니터링**
   - 시뮬레이터 제어 API 호출을 로깅하고 이상 활동 감지
   - 정기적인 보안 감사

#### Docker 소켓 없이 실행

시뮬레이터 제어 기능이 필요 없다면 Docker 소켓 마운팅을 제거하세요:

```yaml
# docker-compose.yml
services:
  modbus-controller-multi:
    # volumes에서 다음 라인 제거:
    # - /var/run/docker.sock:/var/run/docker.sock
```

**참고**: Docker 소켓을 제거하면 웹 UI의 "시뮬레이터 제어" 기능이 작동하지 않습니다.

### 기타 보안 고려사항

- **SECRET_KEY**: `.env` 파일의 `SECRET_KEY`를 반드시 변경하세요
- **네트워크 노출**: 필요한 포트만 개방하고 불필요한 외부 접근 차단
- **업데이트**: Python 패키지와 Docker 이미지를 정기적으로 업데이트
- **Rate Limiting**: 내장된 API rate limiting이 활성화되어 있는지 확인

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 버전 이력

### v2.1.0 (2025-12-19)

- 🚴 **UWB 하이패스 시스템**: 이륜차 입출차 자동 감지 및 신호등 제어
- ⚙️ **.env 기반 센서 매핑**: 하드웨어 설정을 코드 변경 없이 .env에서 관리
- ⚡ **25ms 고속 폴링**: 정확한 방향 감지 및 빠른 응답
- 📊 **실시간 통계**: Lane별 입차/출차 횟수 집계
- 🎨 **비주얼 피드백**: 센서 감지 애니메이션, 차량 이동 효과
- 🔧 **입력 검증 강화**: 백엔드/프론트엔드 이중 검증 시스템
- 📝 **JSDoc 타입 정의**: TypeScript 없이 타입 안정성 확보

### v2.0.0 (2025-01-XX)

- 🚀 **멀티 디바이스 지원**: 최대 8대 장비 동시 제어
- 🎨 Glass Morphism UI 디자인
- 📊 통합 모니터링 대시보드
- 🔒 OWASP 기반 보안 강화
- ⚡ SSE 최적화 (변경된 장비만 전송)
- 📝 장비별 독립 로깅
- 🔄 하위 호환성 유지 (레거시 API)

### v1.0.0 (2025-01-XX)

- ✨ 초기 릴리스 (단일 장비 제어)
- 🎨 다크모드 UI
- 🔄 실시간 SSE 업데이트
- 🐳 Docker 지원

## 관련 문서

- [HIPASS_README.md](HIPASS_README.md) - 🚴 UWB 하이패스 시스템 사용 설명서
- [MULTI_DEVICE_ARCHITECTURE_ANALYSIS.md](MULTI_DEVICE_ARCHITECTURE_ANALYSIS.md) - 멀티 디바이스 아키텍처 상세 분석
- [MULTI_DEVICE_SETUP_GUIDE.md](MULTI_DEVICE_SETUP_GUIDE.md) - 멀티 디바이스 설정 가이드
- [CLAUDE.md](CLAUDE.md) - Claude Code 개발 가이드

## 관련 링크

- [CIE-H14A 제품 페이지](https://www.sollae.co.kr/)
- [CIE-H14A 매뉴얼](https://www.sollae.co.kr/ko/download/pds_files/cieh14ako.pdf)
- [Modbus 프로토콜](https://modbus.org/)
- [Flask 문서](https://flask.palletsprojects.com/)
- [pyModbusTCP](https://github.com/sourceperl/pyModbusTCP)

---

**Made with ❤️ for Industrial IoT**

🚀 **v2.0.0 - Now supporting up to 8 devices simultaneously!**

# CIE-H14A Modbus TCP/IP 멀티 제어 시스템 사용자 매뉴얼

**버전:** v2.0.0
**작성일:** 2025년
**대상:** 시스템 관리자, 개발자, 운영자

---

## 목차

1. [시스템 개요](#1-시스템-개요)
2. [시스템 아키텍처](#2-시스템-아키텍처)
3. [설치 및 배포](#3-설치-및-배포)
4. [환경 설정](#4-환경-설정)
5. [사용자 인터페이스](#5-사용자-인터페이스)
6. [API 레퍼런스](#6-api-레퍼런스)
7. [운영 및 모니터링](#7-운영-및-모니터링)
8. [문제 해결](#8-문제-해결)
9. [고급 설정](#9-고급-설정)
10. [보안 및 성능](#10-보안-및-성능)

---

## 1. 시스템 개요

### 1.1 시스템 소개

CIE-H14A Modbus TCP/IP 멀티 제어 시스템은 최대 8대의 CIE-H14A 4채널 디지털 I/O 컨트롤러를 동시에 제어하고 모니터링하는 웹 기반 시스템입니다.

**주요 특징:**
- ✅ **멀티 디바이스 지원**: 최대 8대의 CIE-H14A 장비 동시 제어
- ✅ **실시간 모니터링**: Server-Sent Events(SSE)를 통한 실시간 상태 업데이트
- ✅ **고가용성 설계**: "절대 안 죽는 시스템" - 비동기 큐 기반 아키텍처
- ✅ **자동 재연결**: Modbus 연결 끊김 시 자동 재연결
- ✅ **DI 감지 알림**: 디지털 입력 감지 시 외부 URL 자동 호출
- ✅ **웹 기반 UI**: 모던한 반응형 웹 인터페이스 (Bootstrap 5)
- ✅ **RESTful API**: 외부 시스템 연동을 위한 표준 API
- ✅ **Docker 지원**: 컨테이너 기반 배포 및 관리

### 1.2 기술 스택

| 구분 | 기술 |
|------|------|
| **백엔드** | Python 3.11+, Flask 3.0 |
| **Modbus 통신** | pyModbusTCP 0.2.0 |
| **WSGI 서버** | Gunicorn 21.2.0 |
| **프론트엔드** | HTML5, CSS3, Vanilla JavaScript |
| **UI 프레임워크** | Bootstrap 5.3, Bootstrap Icons |
| **실시간 통신** | Server-Sent Events (SSE) |
| **컨테이너** | Docker, Docker Compose |

### 1.3 시스템 요구사항

#### 하드웨어 요구사항
- **CPU**: 2코어 이상 권장
- **메모리**: 1GB 이상 (장비 4대 기준), 추가 장비당 +128MB
- **네트워크**: 1Gbps Ethernet (Modbus TCP 통신용)

#### 소프트웨어 요구사항
- **운영체제**: Linux (Ubuntu 20.04+), Windows 10+, macOS
- **Python**: 3.11 이상 (로컬 실행 시)
- **Docker**: 20.10 이상 (컨테이너 실행 시)
- **웹 브라우저**: Chrome 90+, Firefox 88+, Edge 90+

---

## 2. 시스템 아키텍처

### 2.1 전체 구조

```
┌─────────────────────────────────────────────────────────────┐
│                      웹 브라우저 (사용자)                     │
│              HTML5 + CSS3 + JavaScript (SSE)                │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP/SSE
┌───────────────────────────▼─────────────────────────────────┐
│                    Flask 애플리케이션                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  routes.py  │  │ validators  │  │ monitoring  │         │
│  │  (API)      │  │             │  │             │         │
│  └──────┬──────┘  └─────────────┘  └─────────────┘         │
│         │                                                   │
│  ┌──────▼──────────────────────────────────────┐           │
│  │        modbus_client.py (CIE_H14A_Client)  │           │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  │           │
│  │  │ Device 1 │  │ Device 2 │  │ Device N │  │           │
│  │  │ 폴링스레드│  │ 폴링스레드│  │ 폴링스레드│  │           │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  │           │
│  └───────┼─────────────┼─────────────┼─────────┘           │
└──────────┼─────────────┼─────────────┼─────────────────────┘
           │             │             │
           │ Modbus TCP  │ Modbus TCP  │ Modbus TCP
           │ (FC 02/05)  │ (FC 02/05)  │ (FC 02/05)
           │             │             │
┌──────────▼─────┐ ┌─────▼──────┐ ┌───▼─────────┐
│  CIE-H14A #1   │ │ CIE-H14A #2│ │ CIE-H14A #N │
│  DI0-DI3       │ │ DI0-DI3    │ │ DI0-DI3     │
│  DO0-DO3       │ │ DO0-DO3    │ │ DO0-DO3     │
└────────────────┘ └────────────┘ └─────────────┘
```

### 2.2 핵심 아키텍처 원칙

#### "절대 안 죽는 시스템" 설계
1. **비동기 큐 기반 제어**
   - API 요청은 항상 즉시 응답 (200ms 이내)
   - Modbus 쓰기 명령은 큐에 추가 후 백그라운드 처리
   - 타임아웃이 발생해도 시스템은 계속 동작

2. **스레드 분리**
   - **메인 스레드**: Flask 웹 서버, API 요청 처리
   - **폴링 스레드** (장비당 1개): Modbus 읽기/쓰기 전용
   - **SSE 스레드**: 클라이언트 실시간 업데이트

3. **자동 복구 메커니즘**
   - Modbus 연결 끊김 → 자동 재연결 (지수 백오프)
   - 폴링 오류 → 로깅 후 계속 진행
   - 타임아웃 → 재시도 (최대 3회)

### 2.3 데이터 흐름

#### 입력 모니터링 (DI 읽기)
```
폴링 스레드 (25ms 주기)
  ↓
Modbus FC 02 (Read Discrete Inputs, Address 0-3)
  ↓
내부 상태 업데이트 (Lock)
  ↓
DI 감지 확인 (선택사항: 외부 URL 호출)
  ↓
SSE 스트림으로 웹 클라이언트에 전송 (200ms 주기)
```

#### 출력 제어 (DO 쓰기)
```
웹 UI 버튼 클릭
  ↓
POST /api/devices/{device_id}/output/{channel}
  ↓
출력 명령 큐에 추가 (즉시 응답)
  ↓
폴링 스레드가 큐에서 명령 꺼내기
  ↓
Modbus FC 05 (Write Single Coil, Address 8-11)
  ↓
재시도 메커니즘 (최대 3회, 100ms 간격)
  ↓
성공 시: 내부 상태 업데이트, 자동 꺼짐 타이머 시작
  ↓
SSE 스트림으로 웹 클라이언트에 전송
```

### 2.4 Modbus 레지스터 매핑 (CIE-H14A)

| 채널 | 타입 | Function Code | Address | 설명 |
|------|------|---------------|---------|------|
| DI0 | 입력 | 02 (Read Discrete Inputs) | 0 | 디지털 입력 0 |
| DI1 | 입력 | 02 | 1 | 디지털 입력 1 |
| DI2 | 입력 | 02 | 2 | 디지털 입력 2 |
| DI3 | 입력 | 02 | 3 | 디지털 입력 3 |
| DO0 | 출력 | 05 (Write Single Coil) | 8 | 디지털 출력 0 (릴레이) |
| DO1 | 출력 | 05 | 9 | 디지털 출력 1 (릴레이) |
| DO2 | 출력 | 05 | 10 | 디지털 출력 2 (릴레이) |
| DO3 | 출력 | 05 | 11 | 디지털 출력 3 (릴레이) |

**⚠️ 중요:** 출력 주소는 0이 아닌 8부터 시작합니다!

---

## 3. 설치 및 배포

### 3.1 Docker Compose를 이용한 배포 (권장)

#### 사전 준비
```bash
# Docker 및 Docker Compose 설치 확인
docker --version
docker-compose --version
```

#### 설치 단계
```bash
# 1. 프로젝트 디렉토리로 이동
cd MASS_MODBUS

# 2. 환경 설정 파일 생성
cp .env.example .env

# 3. .env 파일 편집 (장비 IP 주소 등 설정)
nano .env  # 또는 메모장

# 4. Docker Compose로 빌드 및 실행
docker-compose up -d

# 5. 로그 확인
docker-compose logs -f modbus-controller

# 6. 웹 브라우저에서 접속
http://localhost:5000
```

#### Docker Compose 주요 명령어
```bash
# 시작
docker-compose up -d

# 중지
docker-compose down

# 재시작
docker-compose restart

# 로그 확인 (실시간)
docker-compose logs -f

# 로그 확인 (최근 100줄)
docker-compose logs --tail=100

# 컨테이너 상태 확인
docker-compose ps

# 재빌드 후 시작
docker-compose up --build -d
```

### 3.2 로컬 Python 환경에서 실행

#### Windows
```powershell
# 1. Python 가상환경 생성
python -m venv venv

# 2. 가상환경 활성화
venv\Scripts\activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 환경 설정 파일 생성
cp .env.example .env

# 5. 애플리케이션 실행
python run.py

# 웹 브라우저에서 http://localhost:5000 접속
```

#### Linux/Mac
```bash
# 1. Python 가상환경 생성
python3 -m venv venv

# 2. 가상환경 활성화
source venv/bin/activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 환경 설정 파일 생성
cp .env.example .env

# 5. 애플리케이션 실행
python run.py

# 웹 브라우저에서 http://localhost:5000 접속
```

### 3.3 프로덕션 배포 (Gunicorn)

```bash
# Gunicorn으로 프로덕션 서버 실행
gunicorn --bind 0.0.0.0:5000 \
         --workers 1 \
         --threads 20 \
         --timeout 300 \
         --graceful-timeout 30 \
         --keep-alive 5 \
         --access-logfile - \
         --error-logfile - \
         "app:create_app()"
```

**중요 설정:**
- `--workers 1`: 단일 워커 (Modbus 연결 충돌 방지)
- `--threads 20`: 멀티 디바이스 + SSE 연결을 위한 충분한 스레드
- `--timeout 300`: 긴 SSE 연결을 위한 타임아웃

---

## 4. 환경 설정

### 4.1 .env 파일 구조

`.env` 파일은 시스템의 모든 설정을 관리합니다. `.env.example` 파일을 복사하여 수정하세요.

#### 기본 설정
```bash
# Flask 설정
FLASK_ENV=production
SECRET_KEY=your-secret-key-change-this
FLASK_HOST=0.0.0.0
FLASK_PORT=5000

# 로깅
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

#### 전역 Modbus 기본값
모든 장비에 공통으로 적용되는 기본 설정입니다.

```bash
MODBUS_DEFAULT_UNIT_ID=1
MODBUS_DEFAULT_TIMEOUT=0.3          # Modbus 타임아웃 (초)
MODBUS_DEFAULT_POLL_INTERVAL=0.025  # DI 폴링 주기 (초, 25ms=고속 감지)
MODBUS_DEFAULT_AUTO_OFF_TIME=1.0   # DO 자동 꺼짐 시간 (초, 0=비활성화)
MODBUS_DEFAULT_RETRY_COUNT=3       # 제어 실패 시 재시도 횟수
MODBUS_DEFAULT_RETRY_DELAY=0.1     # 재시도 간 대기 시간 (초)
```

#### 센서 URL 설정 (DI 감지 알림)
```bash
# 공통 센서 URL (모든 장비에 적용)
SENSOR_URL=http://localhost:5000/api/get_sensor

# 장비별 개별 센서 URL (선택사항)
DEVICE1_SENSOR_URL=http://192.168.10.100/sensor1
DEVICE2_SENSOR_URL=http://192.168.10.100/sensor2
```

### 4.2 장비 설정

최대 8대의 장비를 설정할 수 있습니다.

#### 장비 1 설정 예시
```bash
DEVICE1_ENABLED=true                # 활성화 여부 (필수)
DEVICE1_NAME=Lane1                  # 장비 이름 (웹 UI에 표시)
DEVICE1_HOST=192.168.10.101         # IP 주소 (필수)
DEVICE1_PORT=502                    # 포트 (선택, 기본값: 502)
DEVICE1_UNIT_ID=1                   # Unit ID (선택, 기본값: 전역 설정)
DEVICE1_TIMEOUT=0.3                 # 타임아웃 (선택, 기본값: 전역 설정)
DEVICE1_POLL_INTERVAL=0.1           # 폴링 주기 (선택)
DEVICE1_AUTO_OFF_TIME=1.0           # 자동 꺼짐 (선택)
DEVICE1_RETRY_COUNT=3               # 재시도 횟수 (선택)
DEVICE1_RETRY_DELAY=0.1             # 재시도 간격 (선택)
DEVICE1_SENSOR_URL=http://...       # 센서 URL (선택)
```

#### 장비 2-8 설정
```bash
# 장비 2
DEVICE2_ENABLED=true
DEVICE2_NAME=Lane2
DEVICE2_HOST=192.168.10.102

# 장비 3
DEVICE3_ENABLED=true
DEVICE3_NAME=Lane3
DEVICE3_HOST=192.168.10.103

# 장비 4
DEVICE4_ENABLED=true
DEVICE4_NAME=Lane4
DEVICE4_HOST=192.168.10.104

# 장비 5-8 (필요 시)
# DEVICE5_ENABLED=true
# DEVICE5_NAME=Lane5
# DEVICE5_HOST=192.168.10.105
```

### 4.3 주요 파라미터 설명

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `POLL_INTERVAL` | 0.025초 | DI 폴링 주기 (짧을수록 빠른 감지, CPU 사용량 증가) |
| `TIMEOUT` | 0.3초 | Modbus 통신 타임아웃 (너무 짧으면 연결 불안정) |
| `AUTO_OFF_TIME` | 1.0초 | DO ON 후 자동으로 OFF되는 시간 (0=비활성화) |
| `RETRY_COUNT` | 3회 | 제어 실패 시 재시도 횟수 |
| `RETRY_DELAY` | 0.1초 | 재시도 간 대기 시간 |

### 4.4 네트워크 확인

장비 설정 후 네트워크 연결을 확인하세요.

```bash
# 각 장비에 ping 테스트
ping 192.168.10.101
ping 192.168.10.102
ping 192.168.10.103
ping 192.168.10.104

# Modbus 포트 확인 (Linux/Mac)
nc -zv 192.168.10.101 502

# Windows에서 포트 확인
Test-NetConnection -ComputerName 192.168.10.101 -Port 502
```

---

## 5. 사용자 인터페이스

### 5.1 메인 대시보드

웹 브라우저에서 `http://localhost:5000` 접속 시 표시되는 메인 화면입니다.

#### 상단 네비게이션 바
- **로고**: 경우시스테크(Kyungwoo) 로고 표시
- **제목**: "CIE-H14A Modbus 멀티 제어 시스템"
- **API 문서 버튼**: API 문서 페이지로 이동
- **연결 상태**: 전체 장비 연결 상태 표시
  - 🟢 녹색: 전체 연결됨
  - 🟡 노란색: 일부 연결됨
  - 🔴 빨간색: 전체 연결 끊김

#### API 모니터링 카드
시스템 전체의 실시간 성능 지표를 표시합니다.

- **가동 시간**: 시스템 가동 시간
- **활성 장비**: 연결된 장비 수 / 전체 장비 수
- **총 요청**: API 총 요청 수
- **성공률**: API 요청 성공률 (%)
- **1분 요청**: 최근 1분간 요청 수
- **평균 응답**: 평균 응답 시간 (ms)

#### 장비 카드 (각 장비별)
각 CIE-H14A 장비마다 개별 카드가 표시됩니다.

**카드 헤더:**
- 장비 이름 (예: Lane1, Lane2)
- IP 주소
- 연결 상태 배지

**디지털 입력 (DI) 섹션:**
- 4개의 LED 인디케이터 (DI0-DI3)
- 🔴 빨간색: ON 상태
- ⚪회색: OFF 상태
- 실시간 상태 업데이트 (25ms 고속 폴링)

**디지털 출력 (DO) 섹션:**
- 4개의 제어 버튼 (DO0-DO3)
- 🟡 노란색: ON 상태
- ⚪ 회색: OFF 상태
- 클릭 시 토글 제어

**DI 감지 상태 (센서 URL 설정 시):**
- 🟢 녹색: DI 수신 대기
- 🟡 노란색: 요청 전송 중
- 🔴 빨간색: DI 감지 - 종료 대기
- 전송된 GET 요청 URL 표시

#### 시스템 로그
- 최근 100개의 시스템 이벤트 표시
- 로그 레벨별 색상 구분
  - 🔵 INFO: 파란색
  - 🟡 WARNING: 노란색
  - 🔴 ERROR: 빨간색
  - 🟢 SUCCESS: 녹색

### 5.2 사용 방법

#### DO (디지털 출력) 제어
1. 장비 카드에서 원하는 DO 버튼 클릭
2. 즉시 상태 반전 (ON ↔ OFF)
3. 자동 꺼짐 설정 시: ON 후 지정 시간 후 자동 OFF
4. 시스템 로그에 제어 내역 기록

#### DI (디지털 입력) 모니터링
1. DI 상태는 자동으로 100ms 주기로 업데이트
2. DI가 ON 상태가 되면 LED가 빨간색으로 변경
3. 센서 URL 설정 시: DI 감지 시 자동으로 GET 요청 전송
4. DI 감지 상태 배지에서 전송 상태 확인 가능

#### 실시간 업데이트
- SSE(Server-Sent Events) 연결로 자동 업데이트
- 연결 끊김 시 자동 재연결 (지수 백오프)
- 페이지 새로고침 없이 실시간 반영

---

## 6. API 레퍼런스

### 6.1 공통 사항

- **Base URL**: `http://<서버_IP>:5000`
- **Content-Type**: `application/json`
- **인증**: 현재 버전은 인증 미구현 (향후 추가 예정)
- **Rate Limiting**:
  - 시스템 전체: 500 req/min
  - 상태 조회: 60 req/min
  - 출력 제어: 120 req/min

### 6.2 장비 관리 API

#### GET /api/devices
활성화된 장비 목록 조회

**Response:**
```json
{
  "devices": [
    {
      "id": "device1",
      "name": "Lane1",
      "host": "192.168.10.101",
      "connected": true
    },
    {
      "id": "device2",
      "name": "Lane2",
      "host": "192.168.10.102",
      "connected": false
    }
  ]
}
```

#### GET /api/status
전체 장비 상태 조회

**Response:**
```json
{
  "devices": {
    "device1": {
      "connected": true,
      "inputs": [false, true, false, false],
      "outputs": [true, false, false, false],
      "timestamp": 1234567890.123,
      "name": "Lane1",
      "di_detection": {
        "enabled": true,
        "di_triggered": false,
        "request_sent": false,
        "sensor_url": "http://localhost:5000/api/get_sensor",
        "device_id": "device1",
        "di_states": [false, false, false, false]
      }
    },
    "device2": { ... }
  },
  "summary": {
    "total_devices": 4,
    "connected_devices": 3,
    "disconnected_devices": 1
  }
}
```

#### GET /api/devices/{device_id}/status
특정 장비 상태 조회

**Parameters:**
- `device_id` (path): 장비 ID (예: device1, device2)

**Response:**
```json
{
  "connected": true,
  "inputs": [false, true, false, false],
  "outputs": [true, false, false, false],
  "timestamp": 1234567890.123,
  "name": "Lane1",
  "di_detection": { ... }
}
```

### 6.3 출력 제어 API

#### POST /api/devices/{device_id}/output/{channel}
특정 장비의 출력 채널 제어

**Parameters:**
- `device_id` (path): 장비 ID
- `channel` (path): 출력 채널 번호 (0-3)

**Request Body:**
```json
{
  "state": true  // true=ON, false=OFF
}
```

**Response (성공):**
```json
{
  "success": true,
  "device_id": "device1",
  "channel": 0,
  "state": true
}
```

**Response (실패):**
```json
{
  "error": "Output control failed",
  "device_id": "device1",
  "channel": 0
}
```

#### POST /api/devices/{device_id}/output/{channel}/toggle
출력 채널 토글 (ON ↔ OFF)

**Parameters:**
- `device_id` (path): 장비 ID
- `channel` (path): 출력 채널 번호 (0-3)

**Response:**
```json
{
  "success": true,
  "device_id": "device1",
  "channel": 0,
  "state": false  // 토글 후 새로운 상태
}
```

### 6.4 GET 방식 제어 API (간편 제어용)

웹 브라우저에서 URL로 직접 제어할 수 있는 간편 API입니다.

#### GET /api/devices/{device_id}/output/{channel}/set?state={on|off}
출력 채널 제어 (GET 방식)

**Parameters:**
- `device_id` (path): 장비 ID
- `channel` (path): 출력 채널 번호 (0-3)
- `state` (query): on/off, 1/0, true/false

**예시:**
```
http://localhost:5000/api/devices/device2/output/1/set?state=on
http://localhost:5000/api/devices/device2/output/1/set?state=off
http://localhost:5000/api/devices/device2/output/1/set?state=1
http://localhost:5000/api/devices/device2/output/1/set?state=0
```

#### GET /api/devices/{device_id}/output/{channel}/on
출력 켜기 (GET 방식)

**예시:**
```
http://localhost:5000/api/devices/device2/output/1/on
```

#### GET /api/devices/{device_id}/output/{channel}/off
출력 끄기 (GET 방식)

**예시:**
```
http://localhost:5000/api/devices/device2/output/1/off
```

### 6.5 실시간 업데이트 API

#### GET /api/events
Server-Sent Events (SSE) 스트림

**Response (초기 상태):**
```
data: {"type": "initial", "devices": { ... }}
```

**Response (업데이트):**
```
data: {"type": "update", "devices": { "device1": { ... } }}
```

**클라이언트 예시 (JavaScript):**
```javascript
const eventSource = new EventSource('/api/events');

eventSource.onmessage = function(event) {
  const data = JSON.parse(event.data);

  if (data.type === 'initial') {
    // 초기 상태 처리
    console.log('Initial state:', data.devices);
  } else if (data.type === 'update') {
    // 업데이트 처리 (변경된 장비만 포함)
    console.log('Update:', data.devices);
  }
};

eventSource.onerror = function() {
  // 재연결 처리
  eventSource.close();
  setTimeout(() => connectSSE(), 2000);
};
```

### 6.6 모니터링 API

#### GET /health
헬스 체크

**Response:**
```json
{
  "status": "healthy",
  "modbus_connected": true,
  "total_devices": 4,
  "connected_devices": 3
}
```

#### GET /api/monitor
API 모니터링 정보

**Response:**
```json
{
  "uptime": 3600.5,
  "total_requests": 15234,
  "failed_requests": 12,
  "success_rate": 99.92,
  "recent_1min": {
    "requests": 45,
    "failed": 0,
    "avg_duration_ms": 12.5
  },
  "recent_history": [
    {
      "timestamp": 1234567890.123,
      "path": "/api/status",
      "status": 200,
      "duration": 15.3,
      "success": true
    }
  ],
  "last_check": 1234567890.123
}
```

### 6.7 센서 엔드포인트

#### GET /api/get_sensor
DI 감지 시 호출되는 엔드포인트

**Query Parameters:**
- `id`: 장비 ID (예: device1)
- `di_states`: DI 상태 (CSV 형식, 예: "1,0,0,0")
- `time`: 밀리초 단위 타임스탬프

**예시:**
```
http://localhost:5000/api/get_sensor?id=device1&di_states=1,0,0,0&time=1234567890123
```

**Response:**
```json
{
  "status": "ok",
  "id": "device1",
  "di": "1,0,0,0",
  "time": 1234567890123
}
```

### 6.8 에러 응답

#### 400 Bad Request
```json
{
  "error": "Invalid input",
  "message": "Channel must be between 0 and 3"
}
```

#### 404 Not Found
```json
{
  "error": "Device not found"
}
```

#### 429 Too Many Requests
```json
{
  "error": "Rate limit exceeded",
  "message": "Too many requests. Please try again later.",
  "retry_after": 60,
  "current_requests": 520
}
```

#### 500 Internal Server Error
```json
{
  "error": "Output control failed",
  "device_id": "device1",
  "channel": 0
}
```

---

## 7. 운영 및 모니터링

### 7.1 로그 관리

#### 로그 레벨
`.env` 파일에서 `LOG_LEVEL` 설정:
- `DEBUG`: 디버깅 정보 (개발용)
- `INFO`: 일반 정보 (기본값)
- `WARNING`: 경고 메시지
- `ERROR`: 에러 메시지
- `CRITICAL`: 치명적 오류

#### Docker 로그 확인
```bash
# 실시간 로그
docker-compose logs -f modbus-controller

# 최근 100줄
docker-compose logs --tail=100 modbus-controller

# 특정 시간 이후 로그
docker-compose logs --since "2025-01-01T00:00:00" modbus-controller
```

#### 로그 파일 위치
Docker 컨테이너 내부:
- **경로**: `/var/lib/docker/containers/<container_id>/<container_id>-json.log`
- **최대 크기**: 10MB
- **최대 파일 수**: 3개 (자동 로테이션)

### 7.2 성능 모니터링

#### 웹 UI에서 모니터링
메인 대시보드의 "API 모니터링" 카드에서 실시간 확인:
- 가동 시간
- 활성 장비 수
- 총 요청 수
- 성공률
- 평균 응답 시간

#### API로 모니터링
```bash
# curl로 모니터링 정보 조회
curl http://localhost:5000/api/monitor

# jq로 예쁘게 출력
curl http://localhost:5000/api/monitor | jq

# 주기적으로 확인 (5초마다)
watch -n 5 'curl -s http://localhost:5000/api/monitor | jq'
```

#### Docker 리소스 사용량
```bash
# 컨테이너 리소스 사용량
docker stats modbus-controller-multi

# 메모리 사용량만
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}"
```

### 7.3 백업 및 복구

#### 설정 백업
```bash
# .env 파일 백업
cp .env .env.backup.$(date +%Y%m%d)

# 전체 프로젝트 백업
tar -czf mass_modbus_backup_$(date +%Y%m%d).tar.gz \
    .env docker-compose.yml app/ config/
```

#### 복구
```bash
# .env 파일 복구
cp .env.backup.20250101 .env

# 재시작
docker-compose down
docker-compose up -d
```

### 7.4 업데이트

#### 코드 업데이트
```bash
# 1. Git으로 최신 코드 받기
git pull origin master

# 2. 재빌드 및 재시작
docker-compose down
docker-compose up --build -d

# 3. 로그 확인
docker-compose logs -f modbus-controller
```

#### Python 패키지 업데이트
```bash
# requirements.txt 수정 후
docker-compose build --no-cache
docker-compose up -d
```

---

## 8. 문제 해결

### 8.1 일반적인 문제

#### 문제: Modbus 연결 실패
**증상:**
- 웹 UI에서 "연결 끊김" 표시
- 로그에 "Modbus 연결 실패" 메시지

**해결 방법:**
1. 네트워크 연결 확인
   ```bash
   ping 192.168.10.101
   ```

2. Modbus 포트 확인
   ```bash
   # Linux/Mac
   nc -zv 192.168.10.101 502

   # Windows
   Test-NetConnection -ComputerName 192.168.10.101 -Port 502
   ```

3. CIE-H14A 장비 설정 확인
   - ezManager 도구로 Modbus TCP 활성화 확인
   - IP 주소 확인
   - Unit ID 확인

4. 방화벽 확인
   ```bash
   # Linux
   sudo ufw allow 502/tcp

   # Windows
   # 방화벽 설정에서 TCP 포트 502 허용
   ```

#### 문제: SSE 연결 끊김
**증상:**
- 웹 UI에서 실시간 업데이트 안 됨
- 콘솔에 "SSE 재연결 시도" 메시지

**해결 방법:**
1. 브라우저 새로고침 (Ctrl+F5)
2. 프록시 서버 타임아웃 설정 확인
3. 네트워크 안정성 확인

#### 문제: Docker 컨테이너 시작 실패
**증상:**
- `docker-compose up` 실행 시 에러

**해결 방법:**
1. 로그 확인
   ```bash
   docker-compose logs
   ```

2. .env 파일 검증
   ```bash
   # 필수 항목 확인
   grep DEVICE1_ENABLED .env
   grep DEVICE1_HOST .env
   ```

3. 포트 충돌 확인
   ```bash
   # Linux/Mac
   lsof -i :5000

   # Windows
   netstat -ano | findstr :5000
   ```

4. 재시작
   ```bash
   docker-compose down
   docker-compose up -d
   ```

#### 문제: 출력 제어 실패
**증상:**
- DO 버튼 클릭 시 상태가 변경되지 않음
- 로그에 "출력 제어 실패" 메시지

**해결 방법:**
1. Modbus 연결 상태 확인
2. 채널 번호 확인 (0-3)
3. 재시도 설정 확인
   ```bash
   # .env 파일
   MODBUS_DEFAULT_RETRY_COUNT=3
   MODBUS_DEFAULT_RETRY_DELAY=0.1
   ```

4. 타임아웃 증가
   ```bash
   # .env 파일
   MODBUS_DEFAULT_TIMEOUT=1.0  # 0.3 → 1.0으로 증가
   ```

### 8.2 로그 분석

#### 정상 로그 패턴
```
[INFO] Modbus 연결 성공: 192.168.10.101:502
[INFO] 폴링 스레드 시작
[INFO] 출력 제어 성공: 채널 0 (주소 8) -> ON
```

#### 경고 로그
```
[WARNING] 재연결 실패 (연속 3회)
[WARNING] 출력 제어 실패: 채널 0 (주소 8) -> ON
```

#### 에러 로그
```
[ERROR] Modbus 연결 예외: [Errno 111] Connection refused
[ERROR] 입력 읽기 예외: Timeout
[CRITICAL] 폴링 루프 연속 10회 실패 - 10초 대기 후 재시도
```

### 8.3 디버깅 모드

#### 디버그 로그 활성화
```bash
# .env 파일
LOG_LEVEL=DEBUG
```

재시작:
```bash
docker-compose restart
docker-compose logs -f
```

#### Python 디버거 사용 (로컬 실행 시)
```python
# run.py에 추가
import pdb; pdb.set_trace()
```

---

## 9. 고급 설정

### 9.1 DI 감지 및 센서 연동

#### 센서 URL 설정
DI(디지털 입력)가 감지되면 자동으로 외부 URL을 호출합니다.

**전역 설정 (.env):**
```bash
SENSOR_URL=http://192.168.10.100/api/sensor
```

**장비별 개별 설정:**
```bash
DEVICE1_SENSOR_URL=http://192.168.10.100/sensor1
DEVICE2_SENSOR_URL=http://192.168.10.100/sensor2
```

#### 동작 원리
1. DI가 하나라도 ON 상태가 되면
2. 즉시 센서 URL로 GET 요청 전송
3. 요청 파라미터:
   - `id`: 장비 ID (예: device1)
   - `di_states`: DI 상태 (CSV, 예: "1,0,0,0")
   - `time`: 밀리초 단위 타임스탬프

4. 모든 DI가 OFF가 되면 전송 가능 상태로 리셋

#### 예시 요청
```
GET http://192.168.10.100/api/sensor?id=device1&di_states=1,0,0,0&time=1234567890123
```

#### 센서 서버 구현 예시 (Python Flask)
```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/api/sensor', methods=['GET'])
def sensor_endpoint():
    device_id = request.args.get('id')
    di_states = request.args.get('di_states')
    timestamp = request.args.get('time')

    print(f"[센서 감지] Device: {device_id}, DI: {di_states}, Time: {timestamp}")

    # 여기에 원하는 처리 로직 추가
    # 예: 데이터베이스 저장, 알림 전송 등

    return jsonify({
        'status': 'ok',
        'id': device_id,
        'di': di_states,
        'time': timestamp
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
```

### 9.2 자동 꺼짐 기능

DO(디지털 출력)를 ON으로 설정한 후 지정된 시간이 지나면 자동으로 OFF합니다.

#### 설정 방법
```bash
# .env 파일
MODBUS_DEFAULT_AUTO_OFF_TIME=1.0  # 1초 후 자동 OFF

# 장비별 개별 설정
DEVICE1_AUTO_OFF_TIME=2.0  # 2초 후 자동 OFF
DEVICE2_AUTO_OFF_TIME=0.5  # 0.5초 후 자동 OFF

# 비활성화
DEVICE3_AUTO_OFF_TIME=0    # 자동 꺼짐 비활성화
```

#### 사용 예시
- **펄스 제어**: 짧은 시간만 ON 필요한 경우 (예: 도어 열림 신호)
- **안전 장치**: 실수로 계속 ON 상태 유지 방지
- **에너지 절약**: 불필요한 전력 소비 방지

### 9.3 폴링 주기 최적화

#### 폴링 주기 설정
```bash
# .env 파일
MODBUS_DEFAULT_POLL_INTERVAL=0.025  # 25ms (기본값, 고속 감지용)

# 초고속 응답이 필요한 경우
DEVICE1_POLL_INTERVAL=0.01  # 10ms

# 일반 모니터링
DEVICE2_POLL_INTERVAL=0.05   # 50ms

# 네트워크 부하 감소가 필요한 경우
DEVICE3_POLL_INTERVAL=0.1   # 100ms
```

#### 권장 설정

| 용도 | 폴링 주기 | 응답 시간 | CPU 부하 | 권장 여부 |
|------|----------|---------|---------|---------|
| **출입 관리 시스템** | **25ms** | ~25ms | 보통 | ✅ **권장** |
| 초고속 감지 | 10ms | ~10ms | 높음 | 특수 상황 |
| 일반 모니터링 | 50ms | ~50ms | 낮음 | 보통 |
| 저속 모니터링 | 100ms+ | ~100ms+ | 매우 낮음 | 비권장 |

### 9.4 재시도 메커니즘

출력 제어 실패 시 자동으로 재시도합니다.

```bash
# .env 파일
MODBUS_DEFAULT_RETRY_COUNT=3    # 최대 3회 재시도
MODBUS_DEFAULT_RETRY_DELAY=0.1  # 100ms 간격
```

#### 동작 원리
1. 첫 번째 시도 실패
2. 100ms 대기
3. 두 번째 시도 실패
4. 100ms 대기
5. 세 번째 시도 실패
6. 최종 실패 처리

### 9.5 다중 워커 설정 (주의)

**⚠️ 경고:** 멀티 워커는 권장하지 않습니다!

Modbus는 단일 연결만 지원하므로, 여러 워커가 동일한 장비에 연결하려고 하면 충돌이 발생합니다.

**올바른 설정 (Gunicorn):**
```bash
gunicorn --workers 1 --threads 20 app:create_app()
```

**잘못된 설정:**
```bash
gunicorn --workers 4 app:create_app()  # ❌ 연결 충돌!
```

---

## 10. 보안 및 성능

### 10.1 보안 설정

#### HTTPS 설정 (프로덕션)
Nginx 또는 Apache를 리버스 프록시로 사용하여 HTTPS를 구성하세요.

**Nginx 설정 예시:**
```nginx
server {
    listen 443 ssl;
    server_name modbus.example.com;

    ssl_certificate /etc/ssl/certs/cert.pem;
    ssl_certificate_key /etc/ssl/private/key.pem;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 지원
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 24h;
    }
}
```

#### 보안 헤더
시스템은 OWASP 권장 보안 헤더를 자동으로 추가합니다:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000`
- `Content-Security-Policy: ...`

#### Rate Limiting
API 요청 제한:
- 전체 시스템: 500 req/min
- 상태 조회: 60 req/min
- 출력 제어: 120 req/min

#### CORS 설정
```bash
# .env 파일
ALLOWED_ORIGINS=http://localhost:5000,http://192.168.10.100
```

### 10.2 성능 최적화

#### 연결 타임아웃 최적화
```bash
# .env 파일
MODBUS_DEFAULT_TIMEOUT=0.3  # 빠른 응답
```

- **너무 짧으면**: 연결 불안정, 재시도 증가
- **너무 길면**: 응답 지연, 리소스 낭비

#### 스레드 수 최적화
```bash
# Dockerfile
gunicorn --workers 1 --threads 20 app:create_app()
```

- **최소 스레드**: 장비 수 + SSE 연결 수 + 10
- **권장**: 20개 (장비 8대 + SSE 10개 + 여유 2개)

#### 메모리 사용량
- **기본**: 256MB
- **장비 4대**: 512MB
- **장비 8대**: 1GB

#### Docker 리소스 제한
```yaml
# docker-compose.yml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 1G
    reservations:
      cpus: '0.5'
      memory: 256M
```

### 10.3 네트워크 최적화

#### Keep-Alive 설정
```bash
gunicorn --keep-alive 5 app:create_app()
```

#### SSE 버퍼링 비활성화
응답 헤더에 자동 설정:
```
X-Accel-Buffering: no
Cache-Control: no-cache
```

#### Modbus 통신 최적화
- **병렬 통신**: 각 장비는 독립적인 스레드에서 통신
- **비블로킹**: 출력 제어는 큐 기반으로 비블로킹 처리
- **타임아웃**: 0.3초로 빠른 실패 및 재시도

---

## 부록

### A. CIE-H14A 장비 설정

#### ezManager 도구 사용
1. CIE-H14A 장비에 PC 연결
2. ezManager 실행
3. "Search Device" 클릭
4. Modbus TCP 활성화
5. IP 주소 설정 (고정 IP 권장)
6. Unit ID = 1 설정
7. "Apply" 클릭

### B. 시뮬레이터 사용

테스트 환경에서 실제 장비 없이 시뮬레이터를 사용할 수 있습니다.

```bash
# docker-compose.yml에서 시뮬레이터 포함
docker-compose up -d

# 시뮬레이터 포트: 5020-5023
# .env 파일 설정:
DEVICE1_HOST=modbus-simulator
DEVICE1_PORT=5020
DEVICE2_HOST=modbus-simulator
DEVICE2_PORT=5021
```

### C. 용어 설명

| 용어 | 설명 |
|------|------|
| **Modbus TCP** | 산업용 통신 프로토콜 (TCP/IP 기반) |
| **Function Code** | Modbus 명령 유형 (02=읽기, 05=쓰기) |
| **DI** | Digital Input (디지털 입력) |
| **DO** | Digital Output (디지털 출력, 릴레이) |
| **SSE** | Server-Sent Events (실시간 단방향 통신) |
| **Gunicorn** | Python WSGI HTTP 서버 |
| **Docker** | 컨테이너 기반 가상화 플랫폼 |

### D. 라이선스

이 소프트웨어는 MIT 라이선스를 따릅니다.

### E. 지원 및 문의

- **GitHub**: [프로젝트 리포지토리]
- **Email**: [지원 이메일]
- **문서**: `http://localhost:5000/docs`

---

**문서 버전:** v2.0.0
**최종 업데이트:** 2025년
**작성자:** Claude Code

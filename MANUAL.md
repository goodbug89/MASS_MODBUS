# CIE-H14A Modbus TCP/IP 멀티 제어 시스템 - 사용자 매뉴얼

**버전:** v2.2.0
**최종 수정일:** 2026-02-04
**대상:** 시스템 관리자, 개발자, 운영자

---

## 목차

1. [시스템 개요](#1-시스템-개요)
2. [설치 및 설정](#2-설치-및-설정)
3. [환경 변수 설정](#3-환경-변수-설정)
4. [REST API 레퍼런스](#4-rest-api-레퍼런스)
5. [DI 감지 및 외부 서버 연동](#5-di-감지-및-외부-서버-연동)
6. [웹 인터페이스](#6-웹-인터페이스)
7. [Docker 운영](#7-docker-운영)
8. [로그 모니터링](#8-로그-모니터링)
9. [문제 해결](#9-문제-해결)
10. [부록](#10-부록)

---

## 1. 시스템 개요

### 1.1 소개

CIE-H14A Modbus TCP/IP 멀티 제어 시스템은 최대 8대의 CIE-H14A 4채널 디지털 I/O 컨트롤러를 통합 제어하는 웹 기반 시스템입니다.

### 1.2 주요 기능

| 기능 | 설명 |
|------|------|
| **멀티 디바이스 제어** | 최대 8대의 CIE-H14A 장비 동시 제어 |
| **실시간 모니터링** | SSE 기반 실시간 상태 업데이트 (25ms 주기) |
| **DI 감지 및 외부 연동** | DI 상태 변화 시 외부 서버로 HTTP GET 요청 |
| **자동 DO 제어** | DI0-DI2 시간차 기반 DO3 자동 펄스 제어 |
| **출력 자동 꺼짐** | duration 파라미터로 출력 ON 후 자동 OFF (ms 단위) |
| **REST API** | 완전한 REST API로 외부 시스템 연동 |
| **웹 대시보드** | Bootstrap 기반 반응형 웹 인터페이스 |

### 1.3 기술 스택

- **Backend:** Python 3.11+, Flask 3.0, Gunicorn
- **Modbus:** pyModbusTCP 0.2.0
- **Frontend:** HTML5, CSS3, JavaScript, Bootstrap 5
- **실시간:** Server-Sent Events (SSE)
- **컨테이너:** Docker, Docker Compose

### 1.4 Modbus 레지스터 매핑

| 채널 | 타입 | 기능 코드 | 주소 | 설명 |
|------|------|----------|------|------|
| DI0-DI3 | 입력 | FC 02 | 0-3 | 디지털 입력 (센서) |
| DO0-DO3 | 출력 | FC 05 | 8-11 | 릴레이 출력 (제어) |

---

## 2. 설치 및 설정

### 2.1 요구사항

- Docker Desktop 또는 Docker Engine
- Docker Compose v2.0+
- (선택) Python 3.11+ (로컬 개발 시)

### 2.2 빠른 시작

```bash
# 1. 저장소 클론
git clone https://github.com/goodbug89/MASS_MODBUS.git
cd MASS_MODBUS

# 2. 환경 변수 설정
cp .env.example .env
# .env 파일 편집하여 장비 IP 등 설정

# 3. Docker 컨테이너 시작
docker-compose up -d

# 4. 웹 브라우저에서 접속
# http://localhost:5000
```

### 2.3 로컬 개발 환경

```bash
# 가상환경 생성 및 활성화
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# 의존성 설치
pip install -r requirements.txt

# 개발 서버 실행
python run.py
```

---

## 3. 환경 변수 설정

### 3.1 .env 파일 구조

```bash
# ==============================================================================
# Flask 설정
# ==============================================================================
FLASK_ENV=development          # development | production
SECRET_KEY=your-secret-key     # 보안 키 (프로덕션에서 변경 필수)
FLASK_HOST=0.0.0.0
FLASK_PORT=5000

# ==============================================================================
# Modbus 기본값 (모든 장비에 공통 적용)
# ==============================================================================
MODBUS_DEFAULT_UNIT_ID=1       # Modbus Unit ID
MODBUS_DEFAULT_TIMEOUT=0.3     # 연결 타임아웃 (초)
MODBUS_DEFAULT_POLL_INTERVAL=0.025  # 폴링 주기 (25ms)
MODBUS_DEFAULT_AUTO_OFF_TIME=1.0    # 자동 꺼짐 시간 (초)
MODBUS_DEFAULT_RETRY_COUNT=3   # 재시도 횟수
MODBUS_DEFAULT_RETRY_DELAY=0.1 # 재시도 간격 (초)

# ==============================================================================
# DI 감지 시 외부 서버 호출 URL
# ==============================================================================
SENSOR_URL=http://your-server.com/api/sensor

# ==============================================================================
# 장비별 개별 설정
# ==============================================================================
# 장비 1 (Lane1)
DEVICE1_ENABLED=true
DEVICE1_NAME=Lane1
DEVICE1_HOST=192.168.10.105    # CIE-H14A IP 주소
DEVICE1_PORT=502               # Modbus TCP 포트
DEVICE1_SENSOR_URL=http://server.com/api/lane1  # (선택) 개별 URL

# 장비 2 (Lane2)
DEVICE2_ENABLED=true
DEVICE2_NAME=Lane2
DEVICE2_HOST=192.168.10.106
DEVICE2_PORT=502

# 장비 3-8도 동일한 형식으로 설정 가능
```

### 3.2 주요 환경 변수 설명

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `SENSOR_URL` | DI 감지 시 호출할 외부 서버 URL | - |
| `DEVICE{N}_ENABLED` | 장비 활성화 여부 | false |
| `DEVICE{N}_HOST` | 장비 IP 주소 | - |
| `DEVICE{N}_PORT` | Modbus TCP 포트 | 502 |
| `DEVICE{N}_SENSOR_URL` | 장비별 개별 센서 URL (선택) | SENSOR_URL 사용 |

---

## 4. REST API 레퍼런스

### 4.1 API 기본 정보

- **Base URL:** `http://localhost:5000/api`
- **Content-Type:** `application/json`
- **인증:** 시뮬레이터 제어 API는 `X-API-Key` 헤더 필요

### 4.2 시스템 상태 API

#### GET /api/status
전체 시스템 상태 조회

**응답 예시:**
```json
{
  "devices": {
    "device1": {
      "connected": true,
      "inputs": [false, false, true, false],
      "outputs": [false, false, false, false],
      "name": "Lane1",
      "host": "192.168.10.105"
    }
  },
  "total_devices": 4,
  "connected_devices": 4
}
```

#### GET /health
헬스 체크

**응답 예시:**
```json
{
  "status": "healthy",
  "modbus_connected": true,
  "connected_devices": 4,
  "total_devices": 4
}
```

### 4.3 장비 상태 API

#### GET /api/devices
모든 장비 목록 조회

**응답 예시:**
```json
{
  "devices": [
    {
      "id": "device1",
      "name": "Lane1",
      "host": "192.168.10.105",
      "port": 502,
      "connected": true
    }
  ],
  "count": 4
}
```

#### GET /api/devices/{device_id}/status
특정 장비 상태 조회

**경로 파라미터:**
- `device_id`: 장비 ID (예: device1, device2)

**응답 예시:**
```json
{
  "connected": true,
  "inputs": [false, false, true, false],
  "outputs": [false, false, false, false],
  "name": "Lane1",
  "timestamp": 1699999999.123,
  "di_detection": {
    "enabled": true,
    "di_triggered": false,
    "request_sent": false,
    "sensor_url": "http://server.com/api/sensor",
    "device_id": "device1"
  }
}
```

### 4.4 출력 제어 API

#### POST /api/devices/{device_id}/output/{channel}
출력 상태 설정 (POST 방식)

**경로 파라미터:**
- `device_id`: 장비 ID
- `channel`: 출력 채널 (0-3)

**요청 본문:**
```json
{
  "state": true,
  "duration_ms": 1000
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `state` | boolean | O | 출력 상태 (true=ON, false=OFF) |
| `duration_ms` | integer | X | 자동 꺼짐 시간 (밀리초, 10~3600000) |

> **참고:** `duration_ms`를 지정하고 `state=true`이면, 지정된 시간 후 자동으로 출력이 꺼집니다.

**응답 예시 (duration_ms 없음):**
```json
{
  "success": true,
  "device_id": "device1",
  "channel": 0,
  "state": true
}
```

**응답 예시 (duration_ms 지정):**
```json
{
  "success": true,
  "device_id": "device1",
  "channel": 0,
  "state": true,
  "duration_ms": 1000,
  "auto_off": true
}
```

**사용 예시:**
```bash
# 영구 ON
curl -X POST -H "Content-Type: application/json" \
  -d '{"state": true}' \
  "http://localhost:5000/api/devices/device1/output/0"

# 500ms 후 자동 OFF
curl -X POST -H "Content-Type: application/json" \
  -d '{"state": true, "duration_ms": 500}' \
  "http://localhost:5000/api/devices/device1/output/0"
```

#### GET /api/devices/{device_id}/output/{channel}/on
출력 켜기 (GET 방식)

**쿼리 파라미터:**
| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| `duration` | integer | X | 자동 꺼짐 시간 (밀리초, 10~3600000) |

**응답 예시 (duration 지정):**
```json
{
  "success": true,
  "device_id": "device1",
  "channel": 0,
  "state": true,
  "message": "DO0 turned ON",
  "duration_ms": 500,
  "auto_off": true
}
```

**사용 예시:**
```bash
# 영구 ON
curl "http://localhost:5000/api/devices/device1/output/0/on"

# 500ms 후 자동 OFF
curl "http://localhost:5000/api/devices/device1/output/0/on?duration=500"

# 1초(1000ms) 후 자동 OFF
curl "http://localhost:5000/api/devices/device1/output/0/on?duration=1000"
```

#### GET /api/devices/{device_id}/output/{channel}/off
출력 끄기 (GET 방식)

```bash
curl "http://localhost:5000/api/devices/device1/output/0/off"
```

#### GET /api/devices/{device_id}/output/{channel}/set?state=on|off|1|0|true|false
출력 설정 (GET 쿼리 방식)

```bash
curl "http://localhost:5000/api/devices/device1/output/0/set?state=on"
curl "http://localhost:5000/api/devices/device1/output/0/set?state=1"
curl "http://localhost:5000/api/devices/device1/output/0/set?state=true"
```

#### POST /api/devices/{device_id}/output/{channel}/toggle
출력 토글

```bash
curl -X POST "http://localhost:5000/api/devices/device1/output/0/toggle"
```

### 4.5 실시간 이벤트 API

#### GET /api/events
SSE(Server-Sent Events) 스트림

**사용 예시 (JavaScript):**
```javascript
const eventSource = new EventSource('/api/events');

eventSource.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('상태 업데이트:', data);
    // data.devices.device1.inputs[0] 등으로 접근
};

eventSource.onerror = function(error) {
    console.error('SSE 연결 오류:', error);
    eventSource.close();
};
```

**이벤트 데이터 형식:**
```json
{
  "devices": {
    "device1": {
      "connected": true,
      "inputs": [true, false, true, false],
      "outputs": [false, false, false, true]
    }
  },
  "timestamp": 1699999999.123
}
```

### 4.6 API 응답 코드

| 코드 | 설명 |
|------|------|
| 200 | 성공 |
| 400 | 잘못된 요청 (채널 범위 오류 등) |
| 401 | 인증 필요 (API 키 누락) |
| 403 | 인증 실패 (API 키 불일치) |
| 404 | 리소스 없음 (장비 ID 오류 등) |
| 429 | 요청 제한 초과 |
| 500 | 서버 내부 오류 |
| 503 | Modbus 연결 끊김 |

---

## 5. DI 감지 및 외부 서버 연동

### 5.1 개요

DI(디지털 입력) 상태가 변할 때마다 설정된 외부 서버로 HTTP GET 요청을 자동 전송합니다. **각 DI 채널의 ON/OFF 상태 변화가 개별적으로 전송**됩니다.

### 5.2 요청 형식

DI 상태가 변할 때마다 다음 형식으로 GET 요청이 전송됩니다:

```
GET {SENSOR_URL}?id={device_id}&channel={channel}&state={state}&time={timestamp}
```

**파라미터:**

| 파라미터 | 타입 | 설명 | 예시 |
|---------|------|------|------|
| `id` | string | 장비 ID | `device1` |
| `channel` | int | DI 채널 번호 | `0`, `1`, `2`, `3` |
| `state` | int | 상태 | `1` (ON), `0` (OFF) |
| `time` | long | 감지 시간 (Unix ms) | `1699999999123` |

### 5.3 전송 시나리오 예시

차량이 센서를 통과할 때의 이벤트 시퀀스:

```
시간 13:45:30.100 - DI0 ON (차량 진입)
→ GET http://server.com/api/sensor?id=device1&channel=0&state=1&time=1699999100

시간 13:45:30.800 - DI2 ON (센서 2 통과)
→ GET http://server.com/api/sensor?id=device1&channel=2&state=1&time=1699999800

시간 13:45:31.200 - DI0 OFF (센서 1 벗어남)
→ GET http://server.com/api/sensor?id=device1&channel=0&state=0&time=1699999200

시간 13:45:31.900 - DI2 OFF (센서 2 벗어남)
→ GET http://server.com/api/sensor?id=device1&channel=2&state=0&time=1699999900
```

### 5.4 서버 측 구현 예시

#### Python (Flask)

```python
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# DI 이벤트 저장소
di_events = {}

@app.route('/api/sensor')
def sensor():
    device_id = request.args.get('id')
    channel = int(request.args.get('channel'))
    state = int(request.args.get('state'))
    timestamp = int(request.args.get('time'))

    # 이벤트 저장
    event_key = f"{device_id}_DI{channel}"
    di_events[event_key] = {
        'state': state,
        'time': timestamp,
        'datetime': datetime.fromtimestamp(timestamp / 1000)
    }

    # DI0-DI2 시간차 계산
    di0_key = f"{device_id}_DI0"
    di2_key = f"{device_id}_DI2"

    if di0_key in di_events and di2_key in di_events:
        di0_time = di_events[di0_key]['time']
        di2_time = di_events[di2_key]['time']
        time_delta_ms = abs(di2_time - di0_time)
        print(f"DI0-DI2 시간차: {time_delta_ms}ms")

        # 시간차 기반 처리
        if time_delta_ms < 1500:  # 1.5초 이내
            print("정상 통과 감지!")

    return jsonify({
        'status': 'ok',
        'device': device_id,
        'channel': channel,
        'state': 'ON' if state else 'OFF'
    })

if __name__ == '__main__':
    app.run(port=8080)
```

#### Node.js (Express)

```javascript
const express = require('express');
const app = express();

const diEvents = new Map();

app.get('/api/sensor', (req, res) => {
    const { id, channel, state, time } = req.query;

    // 이벤트 저장
    const eventKey = `${id}_DI${channel}`;
    diEvents.set(eventKey, {
        state: parseInt(state),
        time: parseInt(time),
        datetime: new Date(parseInt(time))
    });

    // DI0-DI2 시간차 계산
    const di0 = diEvents.get(`${id}_DI0`);
    const di2 = diEvents.get(`${id}_DI2`);

    if (di0 && di2) {
        const timeDelta = Math.abs(di2.time - di0.time);
        console.log(`DI0-DI2 시간차: ${timeDelta}ms`);
    }

    res.json({
        status: 'ok',
        device: id,
        channel: parseInt(channel),
        state: parseInt(state) ? 'ON' : 'OFF'
    });
});

app.listen(8080);
```

### 5.5 DI0-DI2 자동 DO3 제어

DI0과 DI2가 1.5초 이내에 감지되면 자동으로 DO3를 0.5초간 켭니다.

**동작 조건:**
- DI0과 DI2 모두 ON 감지
- 시간차 < 1500ms (1.5초)
- 양방향 지원 (DI0→DI2 또는 DI2→DI0)

**동작 시퀀스:**
```
1. DI0 ON (감지)
2. DI2 ON (1.5초 이내)
3. 시간차 계산 → 조건 충족
4. DO3 자동 ON
5. 0.5초 대기
6. DO3 자동 OFF
```

---

## 6. 웹 인터페이스

### 6.1 메인 대시보드

**URL:** `http://localhost:5000`

**기능:**
- 모든 장비의 DI/DO 상태 실시간 모니터링
- DO 출력 수동 제어 (클릭)
- DI0-DI2 시간차 표시
- 시뮬레이터 제어 패널
- 시스템 로그 표시

### 6.2 UWB 하이패스 대시보드

**URL:** `http://localhost:5000/hipass`

**기능:**
- 이륜차 입/출차 감지 모니터링
- 신호등 상태 표시
- 이벤트 로그

### 6.3 API 문서

**URL:** `http://localhost:5000/docs`

**기능:**
- 대화형 API 문서
- API 테스트 기능

---

## 7. Docker 운영

### 7.1 컨테이너 구성

| 컨테이너 | 포트 | 설명 |
|---------|------|------|
| modbus-controller | 5000 | 메인 컨트롤러 |
| modbus-simulator | 5020-5023 | 테스트용 시뮬레이터 |

### 7.2 운영 명령어

```bash
# 시작
docker-compose up -d

# 중지
docker-compose down

# 재시작
docker-compose restart

# 로그 확인
docker-compose logs -f modbus-controller

# 상태 확인
docker-compose ps

# 재빌드 (코드 변경 후)
docker-compose up --build -d
```

### 7.3 배치 파일 사용

Windows 환경에서 제공되는 배치 파일:

| 파일 | 설명 |
|------|------|
| `start.bat` | 컨테이너 시작 |
| `stop.bat` | 컨테이너 중지 |
| `restart.bat` | 재시작 |
| `logs.bat` | 로그 보기 |
| `status.bat` | 상태 확인 |
| `deploy.bat` | 전체 배포 |
| `clean.bat` | 정리 |

---

## 8. 로그 모니터링

### 8.1 Docker 로그 조회

```bash
# 전체 로그
docker-compose logs modbus-controller

# 실시간 로그
docker-compose logs -f modbus-controller

# 최근 100줄
docker-compose logs --tail=100 modbus-controller
```

### 8.2 DI 감지 로그 필터링

```bash
# DI 감지 관련 로그만
docker-compose logs modbus-controller | grep "DI 감지"

# 상태 변화 로그
docker-compose logs modbus-controller | grep "상태 변화"

# HTTP 요청 로그
docker-compose logs modbus-controller | grep "GET 요청"
```

### 8.3 PowerShell 로그 필터링

```powershell
# DI 감지 로그
docker-compose logs modbus-controller | Select-String "DI 감지"

# 실시간 모니터링
docker-compose logs -f modbus-controller 2>&1 | Select-String "DI|상태"
```

### 8.4 로그 레벨

`.env`에서 설정:

```bash
LOG_LEVEL=DEBUG    # 상세 로그
LOG_LEVEL=INFO     # 일반 로그
LOG_LEVEL=WARNING  # 경고만
LOG_LEVEL=ERROR    # 오류만
```

---

## 9. 문제 해결

### 9.1 연결 문제

**증상:** "Modbus 연결 끊김" 표시

**해결:**
1. CIE-H14A 장비 전원 확인
2. 네트워크 연결 확인: `ping 192.168.10.105`
3. 포트 확인: `telnet 192.168.10.105 502`
4. `.env` 파일의 IP/포트 설정 확인
5. 방화벽 설정 확인 (TCP 502 허용)

### 9.2 Docker 문제

**증상:** 컨테이너 시작 실패

**해결:**
```bash
# Docker Desktop 재시작
# 또는
docker-compose down
docker system prune -f
docker-compose up --build -d
```

### 9.3 외부 서버 연동 실패

**증상:** "GET 요청 실패" 로그

**해결:**
1. SENSOR_URL 설정 확인
2. 외부 서버 접근 가능 여부 확인
3. 방화벽/네트워크 설정 확인
4. 외부 서버 로그 확인

### 9.4 429 Too Many Requests

**증상:** Rate Limiting 오류

**원인:** 동일 서버에 너무 많은 요청

**해결:**
- 외부 서버 Rate Limit 설정 조정
- 폴링 주기 조정 (POLL_INTERVAL)

---

## 10. 부록

### 10.1 전체 API 엔드포인트 요약

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| GET | /health | 헬스 체크 |
| GET | /api/status | 전체 상태 |
| GET | /api/devices | 장비 목록 |
| GET | /api/devices/{id}/status | 장비 상태 |
| POST | /api/devices/{id}/output/{ch} | 출력 설정 |
| GET | /api/devices/{id}/output/{ch}/on | 출력 켜기 |
| GET | /api/devices/{id}/output/{ch}/off | 출력 끄기 |
| GET | /api/devices/{id}/output/{ch}/set | 출력 설정 (쿼리) |
| POST | /api/devices/{id}/output/{ch}/toggle | 출력 토글 |
| GET | /api/events | SSE 스트림 |
| GET | /api/config | 설정 조회 |

### 10.2 curl 사용 예시

```bash
# 상태 조회
curl http://localhost:5000/api/devices/device1/status

# DO0 켜기
curl http://localhost:5000/api/devices/device1/output/0/on

# DO0 끄기
curl http://localhost:5000/api/devices/device1/output/0/off

# DO1 토글
curl -X POST http://localhost:5000/api/devices/device1/output/1/toggle

# 상태로 설정
curl "http://localhost:5000/api/devices/device1/output/2/set?state=on"
```

### 10.3 Python 클라이언트 예시

```python
import requests
import time

BASE_URL = "http://localhost:5000/api"

# 상태 조회
def get_status(device_id):
    response = requests.get(f"{BASE_URL}/devices/{device_id}/status")
    return response.json()

# 출력 제어
def set_output(device_id, channel, state):
    response = requests.post(
        f"{BASE_URL}/devices/{device_id}/output/{channel}",
        json={"state": state}
    )
    return response.json()

# 펄스 출력 (0.5초)
def pulse_output(device_id, channel, duration=0.5):
    set_output(device_id, channel, True)
    time.sleep(duration)
    set_output(device_id, channel, False)

# 사용 예시
status = get_status("device1")
print(f"DI 상태: {status['inputs']}")
print(f"DO 상태: {status['outputs']}")

# DO0 펄스
pulse_output("device1", 0)
```

### 10.4 SSE 클라이언트 예시 (Python)

```python
import requests
import json

def sse_monitor():
    url = "http://localhost:5000/api/events"

    with requests.get(url, stream=True) as response:
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data:'):
                    data = json.loads(line[5:])

                    for device_id, status in data['devices'].items():
                        inputs = status['inputs']
                        print(f"{device_id}: DI={inputs}")

                        # DI0 ON 감지
                        if inputs[0]:
                            print(f"  → {device_id} DI0 감지!")

if __name__ == '__main__':
    sse_monitor()
```

### 10.5 파일 구조

```
MASS_MODBUS/
├── app/
│   ├── __init__.py          # Flask 앱 초기화
│   ├── routes.py             # API 라우트
│   ├── modbus_client.py      # Modbus 클라이언트
│   └── static/
│       ├── index.html        # 메인 대시보드
│       ├── hipass.html       # 하이패스 대시보드
│       ├── docs.html         # API 문서
│       ├── css/style.css     # 스타일시트
│       └── js/
│           ├── main.js       # 메인 JavaScript
│           └── hipass.js     # 하이패스 JavaScript
├── config/
│   └── config.py             # 설정 관리
├── tests/
│   └── modbus_simulator.py   # 시뮬레이터
├── .env                      # 환경 변수
├── .env.example              # 환경 변수 예시
├── docker-compose.yml        # Docker 구성
├── Dockerfile                # 컨트롤러 이미지
├── requirements.txt          # Python 의존성
├── README.md                 # 프로젝트 소개
├── MANUAL.md                 # 이 문서
└── CLAUDE.md                 # Claude 가이드
```

---

## 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| v2.1.1 | 2026-02-04 | DI 개별 채널 ON/OFF 전송 기능 추가 |
| v2.1.0 | 2026-01-07 | DI0-DI2 시간차 기반 DO3 자동제어 |
| v2.0.0 | 2025-10-15 | 멀티 디바이스 지원 (최대 8대) |
| v1.0.0 | 2025-09-01 | 초기 버전 |

---

**문의:** 시스템 관련 문의는 담당자에게 연락하세요.

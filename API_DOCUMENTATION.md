# CIE-H14A Modbus Controller API 문서

## 개요

CIE-H14A 4채널 디지털 I/O 컨트롤러를 제어하기 위한 REST API입니다.

**Base URL**: `http://localhost:5000`

**버전**: 1.0.0

**프로토콜**: HTTP/REST

**데이터 포맷**: JSON

---

## 목차

- [인증](#인증)
- [에러 코드](#에러-코드)
- [엔드포인트](#엔드포인트)
  - [Health Check](#1-health-check)
  - [시스템 상태 조회](#2-시스템-상태-조회)
  - [출력 제어](#3-출력-제어)
  - [출력 토글](#4-출력-토글)
  - [설정 조회](#5-설정-조회)
  - [모니터링 정보](#6-모니터링-정보)
  - [실시간 이벤트 스트림 (SSE)](#7-실시간-이벤트-스트림-sse)
- [데이터 모델](#데이터-모델)
- [사용 예제](#사용-예제)

---

## 인증

현재 버전에서는 인증이 필요하지 않습니다.

> **참고**: 프로덕션 환경에서는 적절한 인증 메커니즘(API Key, JWT 등)을 추가해야 합니다.

---

## 에러 코드

| HTTP 상태 코드 | 설명 |
|---------------|------|
| `200` | 성공 |
| `400` | 잘못된 요청 (파라미터 오류) |
| `404` | 리소스를 찾을 수 없음 |
| `500` | 서버 내부 오류 (Modbus 통신 실패 등) |

### 에러 응답 형식

```json
{
  "error": "에러 메시지 설명"
}
```

---

## 엔드포인트

### 1. Health Check

서버 상태 및 Modbus 연결 상태를 확인합니다.

**엔드포인트**: `GET /health`

**응답**:

```json
{
  "status": "healthy",
  "modbus_connected": true
}
```

**필드 설명**:
- `status` (string): 서버 상태 (`"healthy"` 고정)
- `modbus_connected` (boolean): Modbus 연결 상태

**예제**:

```bash
curl http://localhost:5000/health
```

---

### 2. 시스템 상태 조회

전체 입출력(I/O) 상태를 조회합니다.

**엔드포인트**: `GET /api/status`

**응답**:

```json
{
  "connected": true,
  "inputs": [false, true, false, false],
  "outputs": [false, false, true, false],
  "timestamp": 1729166400.123
}
```

**필드 설명**:
- `connected` (boolean): Modbus 연결 상태
- `inputs` (array[boolean]): DI0-DI3 상태 (4개 요소)
  - `true`: ON (High)
  - `false`: OFF (Low)
- `outputs` (array[boolean]): DO0-DO3 상태 (4개 요소)
  - `true`: ON (릴레이 닫힘)
  - `false`: OFF (릴레이 열림)
- `timestamp` (float): UNIX 타임스탬프 (초)

**예제**:

```bash
curl http://localhost:5000/api/status
```

---

### 3. 출력 제어

특정 출력 채널을 ON 또는 OFF로 제어합니다.

**엔드포인트**: `POST /api/output/<channel>`

**경로 파라미터**:
- `channel` (integer): 출력 채널 번호 (0-3)

**요청 본문**:

```json
{
  "state": true
}
```

**필드 설명**:
- `state` (boolean): 출력 상태
  - `true`: ON
  - `false`: OFF

**응답 (성공)**:

```json
{
  "success": true,
  "channel": 0,
  "state": true
}
```

**응답 (실패)**:

```json
{
  "error": "출력 제어 실패",
  "channel": 0,
  "state": true
}
```

**예제**:

```bash
# DO0을 ON으로 설정
curl -X POST http://localhost:5000/api/output/0 \
  -H "Content-Type: application/json" \
  -d '{"state": true}'

# DO2를 OFF로 설정
curl -X POST http://localhost:5000/api/output/2 \
  -H "Content-Type: application/json" \
  -d '{"state": false}'
```

**주의사항**:
- `OUTPUT_AUTO_OFF_TIME` 설정값이 0보다 크면, ON 상태 후 자동으로 OFF됩니다.
- 기본값은 1초입니다.

---

### 4. 출력 토글

특정 출력 채널의 상태를 반전(토글)합니다.

**엔드포인트**: `POST /api/output/<channel>/toggle`

**경로 파라미터**:
- `channel` (integer): 출력 채널 번호 (0-3)

**요청 본문**: 없음

**응답 (성공)**:

```json
{
  "success": true,
  "channel": 1,
  "state": true
}
```

**필드 설명**:
- `success` (boolean): 제어 성공 여부
- `channel` (integer): 제어한 채널 번호
- `state` (boolean): 토글 후 새로운 상태

**예제**:

```bash
# DO1 토글 (OFF → ON 또는 ON → OFF)
curl -X POST http://localhost:5000/api/output/1/toggle
```

---

### 5. 설정 조회

현재 Modbus TCP 연결 설정을 조회합니다.

**엔드포인트**: `GET /api/config`

**응답**:

```json
{
  "modbus_host": "192.168.10.105",
  "modbus_port": 502,
  "modbus_unit_id": 1,
  "modbus_timeout": 0.3,
  "poll_interval": 0.5
}
```

**필드 설명**:
- `modbus_host` (string): Modbus TCP 서버 IP 주소
- `modbus_port` (integer): Modbus TCP 포트
- `modbus_unit_id` (integer): Modbus Unit ID
- `modbus_timeout` (float): 연결 타임아웃 (초)
- `poll_interval` (float): 입력 폴링 간격 (초)

**예제**:

```bash
curl http://localhost:5000/api/config
```

---

### 6. 모니터링 정보

API 서버의 상태 및 통계 정보를 조회합니다.

**엔드포인트**: `GET /api/monitor`

**응답**:

```json
{
  "uptime": 3600.5,
  "total_requests": 1523,
  "failed_requests": 12,
  "success_rate": 99.21,
  "recent_1min": {
    "requests": 15,
    "failed": 0,
    "avg_duration_ms": 12.34
  },
  "recent_history": [
    {
      "timestamp": 1729166400.123,
      "path": "/api/status",
      "status": 200,
      "duration": 15.2,
      "success": true
    }
  ],
  "last_check": 1729166400.123
}
```

**필드 설명**:
- `uptime` (float): 서버 가동 시간 (초)
- `total_requests` (integer): 총 요청 수
- `failed_requests` (integer): 실패한 요청 수
- `success_rate` (float): 성공률 (%)
- `recent_1min` (object): 최근 1분간 통계
  - `requests` (integer): 요청 수
  - `failed` (integer): 실패 수
  - `avg_duration_ms` (float): 평균 응답 시간 (ms)
- `recent_history` (array): 최근 10개 요청 이력
- `last_check` (float): 마지막 확인 시간 (UNIX 타임스탬프)

**예제**:

```bash
curl http://localhost:5000/api/monitor
```

---

### 7. 실시간 이벤트 스트림 (SSE)

Server-Sent Events를 통해 실시간으로 I/O 상태 변화를 수신합니다.

**엔드포인트**: `GET /api/events`

**프로토콜**: Server-Sent Events (SSE)

**Content-Type**: `text/event-stream`

**이벤트 데이터**:

```json
{
  "connected": true,
  "inputs": [false, true, false, false],
  "outputs": [false, false, true, false],
  "timestamp": 1729166400.123
}
```

**특징**:
- 연결 유지 (keep-alive)
- 상태 변화 발생 시에만 전송
- 자동 재연결 지원

**예제 (JavaScript)**:

```javascript
const eventSource = new EventSource('/api/events');

eventSource.onmessage = function(event) {
  const data = JSON.parse(event.data);
  console.log('I/O 상태 업데이트:', data);
};

eventSource.onerror = function(error) {
  console.error('SSE 연결 오류:', error);
  eventSource.close();
};
```

**예제 (curl)**:

```bash
curl -N http://localhost:5000/api/events
```

---

## 데이터 모델

### IOStatus

입출력 상태를 나타냅니다.

```typescript
interface IOStatus {
  connected: boolean;       // Modbus 연결 상태
  inputs: boolean[];        // 디지털 입력 상태 (길이: 4)
  outputs: boolean[];       // 디지털 출력 상태 (길이: 4)
  timestamp: number;        // UNIX 타임스탬프 (초)
}
```

### OutputControlRequest

출력 제어 요청 데이터입니다.

```typescript
interface OutputControlRequest {
  state: boolean;           // 출력 상태 (true: ON, false: OFF)
}
```

### OutputControlResponse

출력 제어 응답 데이터입니다.

```typescript
interface OutputControlResponse {
  success: boolean;         // 제어 성공 여부
  channel: number;          // 채널 번호 (0-3)
  state: boolean;           // 제어 후 상태
}
```

---

## 사용 예제

### Python

```python
import requests

BASE_URL = "http://localhost:5000"

# 1. 상태 조회
response = requests.get(f"{BASE_URL}/api/status")
status = response.json()
print(f"연결 상태: {status['connected']}")
print(f"입력: {status['inputs']}")
print(f"출력: {status['outputs']}")

# 2. DO0 켜기
response = requests.post(
    f"{BASE_URL}/api/output/0",
    json={"state": True}
)
result = response.json()
print(f"DO0 제어 결과: {result}")

# 3. DO1 토글
response = requests.post(f"{BASE_URL}/api/output/1/toggle")
result = response.json()
print(f"DO1 토글 결과: {result['state']}")

# 4. SSE 스트림 수신
import sseclient

response = requests.get(f"{BASE_URL}/api/events", stream=True)
client = sseclient.SSEClient(response)

for event in client.events():
    data = json.loads(event.data)
    print(f"실시간 업데이트: {data}")
```

### JavaScript (Node.js)

```javascript
const axios = require('axios');

const BASE_URL = 'http://localhost:5000';

// 1. 상태 조회
async function getStatus() {
  const response = await axios.get(`${BASE_URL}/api/status`);
  console.log('상태:', response.data);
}

// 2. DO0 켜기
async function turnOnOutput0() {
  const response = await axios.post(`${BASE_URL}/api/output/0`, {
    state: true
  });
  console.log('DO0 제어:', response.data);
}

// 3. DO1 토글
async function toggleOutput1() {
  const response = await axios.post(`${BASE_URL}/api/output/1/toggle`);
  console.log('DO1 토글:', response.data);
}

// 실행
getStatus();
turnOnOutput0();
toggleOutput1();
```

### curl

```bash
#!/bin/bash

BASE_URL="http://localhost:5000"

# 1. Health Check
echo "=== Health Check ==="
curl -s $BASE_URL/health | jq .

# 2. 상태 조회
echo -e "\n=== 상태 조회 ==="
curl -s $BASE_URL/api/status | jq .

# 3. DO0 켜기
echo -e "\n=== DO0 ON ==="
curl -s -X POST $BASE_URL/api/output/0 \
  -H "Content-Type: application/json" \
  -d '{"state": true}' | jq .

# 4. DO1 토글
echo -e "\n=== DO1 토글 ==="
curl -s -X POST $BASE_URL/api/output/1/toggle | jq .

# 5. 모니터링 정보
echo -e "\n=== 모니터링 ==="
curl -s $BASE_URL/api/monitor | jq .

# 6. 설정 조회
echo -e "\n=== 설정 조회 ==="
curl -s $BASE_URL/api/config | jq .
```

---

## 채널 매핑

### 디지털 입력 (DI)

| 채널 | Modbus 주소 | 설명 |
|------|-------------|------|
| DI0 | 0 | 디지털 입력 0 |
| DI1 | 1 | 디지털 입력 1 |
| DI2 | 2 | 디지털 입력 2 |
| DI3 | 3 | 디지털 입력 3 |

### 디지털 출력 (DO)

| 채널 | Modbus 주소 | 설명 |
|------|-------------|------|
| DO0 | 8 | 디지털 출력 0 (릴레이) |
| DO1 | 9 | 디지털 출력 1 (릴레이) |
| DO2 | 10 | 디지털 출력 2 (릴레이) |
| DO3 | 11 | 디지털 출력 3 (릴레이) |

> **중요**: 출력 주소는 8부터 시작합니다 (0이 아님).

---

## 환경 변수 설정

`.env` 파일을 통해 다음 설정을 변경할 수 있습니다:

```bash
# Modbus TCP 설정
MODBUS_HOST=192.168.10.105      # CIE-H14A IP 주소
MODBUS_PORT=502                 # Modbus TCP 포트
MODBUS_UNIT_ID=1                # Modbus Unit ID
MODBUS_TIMEOUT=0.3              # 연결 타임아웃 (초)

# 폴링 설정
POLL_INTERVAL=0.5               # 입력 폴링 간격 (초)

# 출력 자동 꺼짐
OUTPUT_AUTO_OFF_TIME=1.0        # 자동 꺼짐 시간 (초, 0이면 비활성화)

# 재시도 설정
OUTPUT_RETRY_COUNT=3            # 출력 제어 재시도 횟수
OUTPUT_RETRY_DELAY=0.1          # 재시도 간 대기 시간 (초)
```

---

## 버전 히스토리

### v1.0.0 (2025-10-14)
- 초기 릴리즈
- 기본 I/O 제어 기능
- SSE 실시간 업데이트
- API 모니터링 기능

---

## 라이선스

이 프로젝트는 내부 사용을 위한 것입니다.

---

## 지원

문의사항이나 버그 리포트는 개발팀에 문의하세요.

**문서 버전**: 1.0.0
**최종 업데이트**: 2025-10-14

# CIE-H14A Modbus Controller API 문서

## 개요

최대 8대의 CIE-H14A 4채널 디지털 I/O 컨트롤러를 제어하기 위한 REST API입니다.

**Base URL**: `http://localhost:5000`

**버전**: 2.0.0

**프로토콜**: HTTP/REST

**데이터 포맷**: JSON

**주요 기능**:
- 멀티 디바이스 지원 (최대 8대)
- POST/GET 방식 모두 지원
- 실시간 SSE 스트림
- Rate Limiting (500회/분, 전체 시스템 합산)
- DI 감지 자동 알림

---

## 목차

- [인증](#인증)
- [Rate Limiting](#rate-limiting)
- [에러 코드](#에러-코드)
- [엔드포인트](#엔드포인트)
  - [Health Check](#1-health-check)
  - [장비 목록 조회](#2-장비-목록-조회)
  - [시스템 상태 조회](#3-시스템-상태-조회)
  - [특정 장비 상태 조회](#4-특정-장비-상태-조회)
  - [출력 제어 (POST)](#5-출력-제어-post)
  - [출력 제어 (GET)](#6-출력-제어-get)
  - [출력 토글](#7-출력-토글)
  - [센서 엔드포인트](#8-센서-엔드포인트)
  - [설정 조회](#9-설정-조회)
  - [모니터링 정보](#10-모니터링-정보)
  - [실시간 이벤트 스트림 (SSE)](#11-실시간-이벤트-스트림-sse)
- [데이터 모델](#데이터-모델)
- [사용 예제](#사용-예제)

---

## 인증

현재 버전에서는 인증이 필요하지 않습니다.

> **참고**: 프로덕션 환경에서는 적절한 인증 메커니즘(API Key, JWT 등)을 추가해야 합니다.

---

## Rate Limiting

**전체 시스템 합산 방식**: 모든 클라이언트의 요청을 합쳐서 **500회/분** 제한

- 모든 엔드포인트에 적용
- 초과 시 HTTP 429 응답
- 클라이언트별 제한이 아닌 시스템 전체 제한

**429 응답 예시**:
```json
{
  "error": "시스템 요청 한도를 초과했습니다",
  "message": "전체 시스템 요청이 500회/분을 초과했습니다",
  "retry_after": 60,
  "current_requests": 500
}
```

---

## 에러 코드

| HTTP 상태 코드 | 설명 |
|---------------|------|
| `200` | 성공 |
| `400` | 잘못된 요청 (파라미터 오류) |
| `404` | 리소스를 찾을 수 없음 |
| `405` | 허용되지 않는 HTTP 메소드 |
| `415` | 지원하지 않는 Content-Type |
| `429` | Rate Limit 초과 |
| `500` | 서버 내부 오류 (Modbus 통신 실패 등) |

### 에러 응답 형식

```json
{
  "error": "에러 타입",
  "message": "상세한 에러 메시지"
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
  "modbus_connected": true,
  "total_devices": 4,
  "connected_devices": 3
}
```

**필드 설명**:
- `status` (string): 서버 상태 (`"healthy"` 고정)
- `modbus_connected` (boolean): 하나 이상의 장비 연결 여부
- `total_devices` (integer): 전체 장비 수
- `connected_devices` (integer): 연결된 장비 수

**예제**:

```bash
curl http://localhost:5000/health
```

---

### 2. 장비 목록 조회

활성화된 모든 장비의 목록을 조회합니다.

**엔드포인트**: `GET /api/devices`

**응답**:

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

**필드 설명**:
- `id` (string): 장비 ID (`device1` ~ `device8`)
- `name` (string): 장비 이름
- `host` (string): IP 주소 (마스킹 제거됨)
- `connected` (boolean): 현재 연결 상태

**예제**:

```bash
curl http://localhost:5000/api/devices
```

---

### 3. 시스템 상태 조회

모든 장비의 입출력(I/O) 상태를 조회합니다.

**엔드포인트**: `GET /api/status`

**응답**:

```json
{
  "devices": {
    "device1": {
      "name": "Lane1",
      "connected": true,
      "inputs": [false, true, false, false],
      "outputs": [false, false, true, false],
      "timestamp": 1729166400.123,
      "di_detection": {
        "di_triggered": true,
        "request_sent": true,
        "sensor_url": "http://localhost:5000/api/get_sensor",
        "device_id": "device1",
        "di_states": [false, true, false, false]
      }
    },
    "device2": {
      "name": "Lane2",
      "connected": true,
      "inputs": [true, false, false, false],
      "outputs": [false, true, false, true],
      "timestamp": 1729166400.456,
      "di_detection": {
        "di_triggered": false,
        "request_sent": false
      }
    }
  },
  "summary": {
    "total_devices": 4,
    "connected_devices": 2,
    "disconnected_devices": 2
  }
}
```

**필드 설명**:
- `devices` (object): 장비별 상태
  - `name` (string): 장비 이름
  - `connected` (boolean): Modbus 연결 상태
  - `inputs` (array[boolean]): DI0-DI3 상태 (4개 요소)
  - `outputs` (array[boolean]): DO0-DO3 상태 (4개 요소)
  - `timestamp` (float): UNIX 타임스탬프 (초)
  - `di_detection` (object): DI 감지 정보
- `summary` (object): 전체 요약 정보

**예제**:

```bash
curl http://localhost:5000/api/status
```

---

### 4. 특정 장비 상태 조회

특정 장비의 상태만 조회합니다.

**엔드포인트**: `GET /api/devices/<device_id>/status`

**경로 파라미터**:
- `device_id` (string): 장비 ID (`device1` ~ `device8`)

**응답**:

```json
{
  "name": "Lane1",
  "connected": true,
  "inputs": [false, true, false, false],
  "outputs": [false, false, true, false],
  "timestamp": 1729166400.123,
  "di_detection": {
    "di_triggered": true,
    "request_sent": true,
    "sensor_url": "http://localhost:5000/api/get_sensor",
    "device_id": "device1",
    "di_states": [false, true, false, false]
  }
}
```

**예제**:

```bash
curl http://localhost:5000/api/devices/device1/status
```

---

### 5. 출력 제어 (POST)

특정 장비의 출력 채널을 ON 또는 OFF로 제어합니다.

**엔드포인트**: `POST /api/devices/<device_id>/output/<channel>`

**경로 파라미터**:
- `device_id` (string): 장비 ID (`device1` ~ `device8`)
- `channel` (integer): 출력 채널 번호 (0-3)

**요청 헤더**:
- `Content-Type: application/json` (필수)

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
  "device_id": "device1",
  "channel": 0,
  "state": true
}
```

**응답 (실패)**:

```json
{
  "error": "Output control failed",
  "device_id": "device1",
  "channel": 0
}
```

**예제**:

```bash
# DO0을 ON으로 설정
curl -X POST http://localhost:5000/api/devices/device1/output/0 \
  -H "Content-Type: application/json" \
  -d '{"state": true}'

# DO2를 OFF로 설정
curl -X POST http://localhost:5000/api/devices/device1/output/2 \
  -H "Content-Type: application/json" \
  -d '{"state": false}'
```

---

### 6. 출력 제어 (GET)

웹 브라우저에서 직접 URL로 접근하여 출력을 제어할 수 있습니다.

#### 6.1. /on 엔드포인트

**엔드포인트**: `GET /api/devices/<device_id>/output/<channel>/on`

**응답**:

```json
{
  "success": true,
  "device_id": "device1",
  "channel": 0,
  "state": true,
  "message": "DO0 turned ON"
}
```

**예제**:

```bash
curl http://localhost:5000/api/devices/device1/output/0/on
```

웹 브라우저 주소창에 직접 입력:
```
http://localhost:5000/api/devices/device1/output/0/on
```

#### 6.2. /off 엔드포인트

**엔드포인트**: `GET /api/devices/<device_id>/output/<channel>/off`

**응답**:

```json
{
  "success": true,
  "device_id": "device1",
  "channel": 0,
  "state": false,
  "message": "DO0 turned OFF"
}
```

**예제**:

```bash
curl http://localhost:5000/api/devices/device1/output/0/off
```

#### 6.3. /set 엔드포인트 (파라미터 방식)

**엔드포인트**: `GET /api/devices/<device_id>/output/<channel>/set?state=<value>`

**쿼리 파라미터**:
- `state` (string): 출력 상태 (필수)
  - 허용 값: `on`, `off`, `1`, `0`, `true`, `false`

**응답**:

```json
{
  "success": true,
  "device_id": "device1",
  "channel": 0,
  "state": true,
  "message": "DO0 turned ON"
}
```

**에러 응답 (파라미터 누락)**:

```json
{
  "error": "Missing state parameter",
  "message": "Please provide state parameter (on/off, 1/0, true/false)",
  "examples": [
    "/api/devices/device1/output/0/set?state=on",
    "/api/devices/device1/output/0/set?state=off"
  ]
}
```

**예제**:

```bash
# 모두 동일하게 동작
curl http://localhost:5000/api/devices/device1/output/0/set?state=on
curl http://localhost:5000/api/devices/device1/output/0/set?state=1
curl http://localhost:5000/api/devices/device1/output/0/set?state=true

curl http://localhost:5000/api/devices/device1/output/0/set?state=off
curl http://localhost:5000/api/devices/device1/output/0/set?state=0
curl http://localhost:5000/api/devices/device1/output/0/set?state=false
```

---

### 7. 출력 토글

특정 장비의 출력 채널을 반전(토글)합니다.

**엔드포인트**: `POST /api/devices/<device_id>/output/<channel>/toggle`

**경로 파라미터**:
- `device_id` (string): 장비 ID
- `channel` (integer): 출력 채널 번호 (0-3)

**요청 본문**: 없음

**응답 (성공)**:

```json
{
  "success": true,
  "device_id": "device1",
  "channel": 1,
  "state": true
}
```

**필드 설명**:
- `success` (boolean): 제어 성공 여부
- `device_id` (string): 장비 ID
- `channel` (integer): 제어한 채널 번호
- `state` (boolean): 토글 후 새로운 상태

**예제**:

```bash
# device1의 DO1 토글 (OFF → ON 또는 ON → OFF)
curl -X POST http://localhost:5000/api/devices/device1/output/1/toggle
```

---

### 8. 센서 엔드포인트

DI 감지 시 자동으로 호출되는 엔드포인트입니다.

**엔드포인트**: `GET /api/get_sensor`

**쿼리 파라미터**:
- `id` (string): 장비 ID
- `di_states` (string): DI 상태 (CSV 형식, 예: "1,0,0,0")
- `time` (integer): 타임스탬프 (밀리초)

**응답**:

```json
{
  "status": "ok",
  "id": "device1",
  "di": "1,0,0,0",
  "time": 1729166400123
}
```

**예제**:

```bash
curl "http://localhost:5000/api/get_sensor?id=device1&di_states=1,0,0,0&time=1729166400123"
```

**UI 표시**:
- 웹 UI에서 DI 감지 시 전체 URL이 표시됩니다
- URL 형식: `http://localhost:5000/api/get_sensor?id=device1&di_states=1,0,0,0&time=1729166400123`
- DI 입력이 끊어지면 URL 표시도 자동 제거됩니다

---

### 9. 설정 조회

현재 장비 설정을 조회합니다.

**엔드포인트**: `GET /api/config`

**응답**: `/api/devices`와 동일 (하위 호환성)

**예제**:

```bash
curl http://localhost:5000/api/config
```

---

### 10. 모니터링 정보

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
- `recent_history` (array): 최근 10개 요청 이력
- `last_check` (float): 마지막 확인 시간 (UNIX 타임스탬프)

**예제**:

```bash
curl http://localhost:5000/api/monitor
```

---

### 11. 실시간 이벤트 스트림 (SSE)

Server-Sent Events를 통해 실시간으로 모든 장비의 I/O 상태 변화를 수신합니다.

**엔드포인트**: `GET /api/events`

**프로토콜**: Server-Sent Events (SSE)

**Content-Type**: `text/event-stream`

**이벤트 타입**:

#### 초기 이벤트 (initial)

연결 직후 모든 장비의 현재 상태를 전송합니다.

```json
{
  "type": "initial",
  "devices": {
    "device1": {
      "connected": true,
      "inputs": [false, true, false, false],
      "outputs": [false, false, true, false],
      "timestamp": 1729166400.123,
      "di_detection": { ... }
    },
    "device2": { ... }
  }
}
```

#### 업데이트 이벤트 (update)

상태가 변경된 장비만 전송합니다 (대역폭 최적화).

```json
{
  "type": "update",
  "devices": {
    "device1": {
      "connected": true,
      "inputs": [true, false, false, false],
      "outputs": [false, false, true, false],
      "timestamp": 1729166401.234,
      "di_detection": { ... }
    }
  }
}
```

**특징**:
- 연결 유지 (keep-alive)
- 상태 변화 발생 시에만 전송
- 변경된 장비만 전송하여 대역폭 절약
- 자동 재연결 지원
- 200ms 간격으로 폴링

**예제 (JavaScript)**:

```javascript
const eventSource = new EventSource('/api/events');

eventSource.onmessage = function(event) {
  const data = JSON.parse(event.data);

  if (data.type === 'initial') {
    console.log('초기 상태:', data.devices);
  } else if (data.type === 'update') {
    console.log('상태 업데이트:', data.devices);
  }
};

eventSource.onerror = function(error) {
  console.error('SSE 연결 오류:', error);
  // 자동 재연결 시도
};
```

**예제 (curl)**:

```bash
curl -N http://localhost:5000/api/events
```

---

## 데이터 모델

### DeviceStatus

특정 장비의 상태를 나타냅니다.

```typescript
interface DeviceStatus {
  name: string;                 // 장비 이름
  connected: boolean;           // Modbus 연결 상태
  inputs: boolean[];            // 디지털 입력 상태 (길이: 4)
  outputs: boolean[];           // 디지털 출력 상태 (길이: 4)
  timestamp: number;            // UNIX 타임스탬프 (초)
  di_detection?: {              // DI 감지 정보
    di_triggered: boolean;      // DI 트리거 여부
    request_sent: boolean;      // 요청 전송 여부
    sensor_url?: string;        // 센서 URL
    device_id?: string;         // 장비 ID
    di_states?: boolean[];      // 전송된 DI 상태
  };
}
```

### SystemStatus

전체 시스템 상태를 나타냅니다.

```typescript
interface SystemStatus {
  devices: {
    [device_id: string]: DeviceStatus;
  };
  summary: {
    total_devices: number;      // 전체 장비 수
    connected_devices: number;  // 연결된 장비 수
    disconnected_devices: number; // 연결 끊긴 장비 수
  };
}
```

### OutputControlRequest

출력 제어 요청 데이터입니다.

```typescript
interface OutputControlRequest {
  state: boolean;               // 출력 상태 (true: ON, false: OFF)
}
```

### OutputControlResponse

출력 제어 응답 데이터입니다.

```typescript
interface OutputControlResponse {
  success: boolean;             // 제어 성공 여부
  device_id: string;            // 장비 ID
  channel: number;              // 채널 번호 (0-3)
  state: boolean;               // 제어 후 상태
  message?: string;             // 상태 메시지 (GET 방식)
}
```

---

## 사용 예제

### Python

```python
import requests
import time

BASE_URL = "http://localhost:5000"

# 1. 모든 장비 상태 조회
response = requests.get(f"{BASE_URL}/api/status")
status = response.json()

for device_id, device in status['devices'].items():
    print(f"{device['name']}: 연결={device['connected']}, DI={device['inputs']}, DO={device['outputs']}")

# 2. 특정 장비 상태 조회
response = requests.get(f"{BASE_URL}/api/devices/device1/status")
device1 = response.json()
print(f"Device1: {device1}")

# 3. POST 방식으로 device1의 DO0 켜기
response = requests.post(
    f"{BASE_URL}/api/devices/device1/output/0",
    json={"state": True}
)
result = response.json()
print(f"DO0 제어 결과: {result}")

# 4. GET 방식으로 device2의 DO1 켜기
response = requests.get(f"{BASE_URL}/api/devices/device2/output/1/on")
result = response.json()
print(f"DO1 ON 결과: {result}")

# 5. GET 파라미터 방식으로 device2의 DO1 끄기
response = requests.get(f"{BASE_URL}/api/devices/device2/output/1/set?state=off")
result = response.json()
print(f"DO1 OFF 결과: {result}")

# 6. device1의 DO1 토글
response = requests.post(f"{BASE_URL}/api/devices/device1/output/1/toggle")
result = response.json()
print(f"DO1 토글 결과: {result['state']}")

# 7. SSE 스트림 수신
import sseclient
import json

response = requests.get(f"{BASE_URL}/api/events", stream=True)
client = sseclient.SSEClient(response)

for event in client.events():
    data = json.loads(event.data)

    if data['type'] == 'initial':
        print("초기 상태 수신:", data['devices'].keys())
    elif data['type'] == 'update':
        for device_id, device_data in data['devices'].items():
            print(f"{device_id} 업데이트: DI={device_data['inputs']}")
```

### JavaScript (Browser)

```javascript
// 1. 모든 장비 상태 조회
async function getAllDevicesStatus() {
  const response = await fetch('/api/status');
  const data = await response.json();

  console.log('전체 장비 상태:', data);
  return data;
}

// 2. 특정 장비 제어 (POST)
async function controlDeviceOutput(deviceId, channel, state) {
  const response = await fetch(`/api/devices/${deviceId}/output/${channel}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ state })
  });

  const result = await response.json();
  console.log(`${deviceId} DO${channel} 제어:`, result);
  return result;
}

// 3. 특정 장비 제어 (GET - 간편)
async function turnOnDevice(deviceId, channel) {
  const response = await fetch(`/api/devices/${deviceId}/output/${channel}/on`);
  const result = await response.json();
  console.log(result.message);
  return result;
}

// 4. SSE 실시간 모니터링
const eventSource = new EventSource('/api/events');

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.type === 'initial') {
    console.log('초기 상태:', data.devices);
    updateUI(data.devices);
  } else if (data.type === 'update') {
    console.log('업데이트:', data.devices);
    updateChangedDevices(data.devices);
  }
};

eventSource.onerror = (error) => {
  console.error('SSE 오류:', error);
  // 자동 재연결 시도
};

// 5. 웹 브라우저 주소창에서 직접 제어 가능
// http://localhost:5000/api/devices/device1/output/0/on
// http://localhost:5000/api/devices/device1/output/0/off
```

### curl

```bash
#!/bin/bash

BASE_URL="http://localhost:5000"

# 1. Health Check
echo "=== Health Check ==="
curl -s $BASE_URL/health | jq .

# 2. 장비 목록 조회
echo -e "\n=== 장비 목록 ==="
curl -s $BASE_URL/api/devices | jq .

# 3. 전체 상태 조회
echo -e "\n=== 전체 상태 ==="
curl -s $BASE_URL/api/status | jq .

# 4. 특정 장비 상태 조회
echo -e "\n=== Device1 상태 ==="
curl -s $BASE_URL/api/devices/device1/status | jq .

# 5. POST 방식 출력 제어
echo -e "\n=== Device1 DO0 ON (POST) ==="
curl -s -X POST $BASE_URL/api/devices/device1/output/0 \
  -H "Content-Type: application/json" \
  -d '{"state": true}' | jq .

# 6. GET 방식 출력 제어 (/on, /off)
echo -e "\n=== Device1 DO0 ON (GET) ==="
curl -s $BASE_URL/api/devices/device1/output/0/on | jq .

echo -e "\n=== Device1 DO0 OFF (GET) ==="
curl -s $BASE_URL/api/devices/device1/output/0/off | jq .

# 7. GET 파라미터 방식 출력 제어
echo -e "\n=== Device2 DO1 ON (GET ?state=on) ==="
curl -s "$BASE_URL/api/devices/device2/output/1/set?state=on" | jq .

echo -e "\n=== Device2 DO1 OFF (GET ?state=0) ==="
curl -s "$BASE_URL/api/devices/device2/output/1/set?state=0" | jq .

# 8. 토글
echo -e "\n=== Device1 DO1 토글 ==="
curl -s -X POST $BASE_URL/api/devices/device1/output/1/toggle | jq .

# 9. 모니터링 정보
echo -e "\n=== 모니터링 ==="
curl -s $BASE_URL/api/monitor | jq .

# 10. SSE 스트림 (5초간 모니터링)
echo -e "\n=== SSE 스트림 (5초) ==="
timeout 5 curl -N $BASE_URL/api/events
```

---

## 채널 매핑

### 디지털 입력 (DI)

| 채널 | Modbus 주소 | Function Code | 설명 |
|------|-------------|---------------|------|
| DI0 | 0 | FC 02 | 디지털 입력 0 |
| DI1 | 1 | FC 02 | 디지털 입력 1 |
| DI2 | 2 | FC 02 | 디지털 입력 2 |
| DI3 | 3 | FC 02 | 디지털 입력 3 |

### 디지털 출력 (DO)

| 채널 | Modbus 주소 | Function Code | 설명 |
|------|-------------|---------------|------|
| DO0 | 8 | FC 05 | 디지털 출력 0 (릴레이) |
| DO1 | 9 | FC 05 | 디지털 출력 1 (릴레이) |
| DO2 | 10 | FC 05 | 디지털 출력 2 (릴레이) |
| DO3 | 11 | FC 05 | 디지털 출력 3 (릴레이) |

> **중요**: 출력 주소는 8부터 시작합니다 (0이 아님).

---

## 환경 변수 설정

`.env` 파일을 통해 다음 설정을 변경할 수 있습니다:

```bash
# Flask 설정
FLASK_ENV=production
SECRET_KEY=your-secret-key-here
FLASK_HOST=0.0.0.0
FLASK_PORT=5000

# 전역 Modbus 기본값
MODBUS_DEFAULT_PORT=502
MODBUS_DEFAULT_UNIT_ID=1
MODBUS_DEFAULT_TIMEOUT=0.3
MODBUS_DEFAULT_POLL_INTERVAL=0.1      # DI 폴링 간격 (100ms)
MODBUS_DEFAULT_AUTO_OFF_TIME=1.0
MODBUS_DEFAULT_RETRY_COUNT=3
MODBUS_DEFAULT_RETRY_DELAY=0.1

# 센서 URL (DI 감지 시 호출)
SENSOR_URL=http://localhost:5000/api/get_sensor

# 장비 1 설정 (최소 4개 장비 활성화 권장)
DEVICE1_ENABLED=true
DEVICE1_NAME=Lane1
DEVICE1_HOST=192.168.10.101
DEVICE1_PORT=502                      # 선택 (기본값 사용 시 생략 가능)

# 장비 2-8 설정도 동일한 패턴
```

---

## 성능 특징

### DI 폴링 주기

- **기본값**: 100ms (0.1초)
- **최대 지연**: DI 변화 감지까지 최대 100ms
- **실시간성**: 매우 빠른 응답 속도

### Rate Limiting

- **방식**: 전체 시스템 합산
- **제한**: 500회/분
- **목적**: Modbus 장비 보호 및 시스템 안정성

### SSE 업데이트

- **폴링 간격**: 200ms
- **최적화**: 변경된 장비만 전송
- **효율성**: 대역폭 절약

---

## 버전 히스토리

### v2.0.0 (2025-01-XX)
- **멀티 디바이스 지원**: 최대 8대 장비 동시 제어
- **GET 방식 제어 API 추가**: 웹 브라우저 직접 제어 가능
- **Rate Limiting 개선**: 전체 시스템 합산 방식 (500회/분)
- **DI 폴링 주기 개선**: 500ms → 100ms (5배 향상)
- **IP 마스킹 제거**: 실제 IP 및 전체 URL 표시
- **DI 감지 개선**: 전체 GET URL 표시 (파라미터 및 밀리초 타임스탬프 포함)
- **장비별 개별 포트 설정**: 유연한 네트워크 구성
- **SSE 최적화**: 변경된 장비만 전송

### v1.0.0 (2025-10-14)
- 초기 릴리즈 (단일 장비)
- 기본 I/O 제어 기능
- SSE 실시간 업데이트
- API 모니터링 기능

---

## 라이선스

MIT License

---

## 지원

문의사항이나 버그 리포트는 개발팀에 문의하세요.

**문서 버전**: 2.0.0
**최종 업데이트**: 2025-01-XX

---

**Made with ❤️ for Industrial IoT**

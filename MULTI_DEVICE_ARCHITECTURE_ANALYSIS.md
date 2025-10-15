# 멀티 디바이스 아키텍처 심층 분석 보고서

**프로젝트**: CIE-H14A Modbus TCP/IP 제어 시스템
**목표**: 1대 → 4대 멀티 디바이스 확장
**작성일**: 2025-10-15
**버전**: 1.0

---

## 📋 목차

1. [현재 시스템 분석](#1-현재-시스템-분석)
2. [요구사항 정의](#2-요구사항-정의)
3. [아키텍처 설계](#3-아키텍처-설계)
4. [설정 파일 스키마](#4-설정-파일-스키마)
5. [API 라우팅 전략](#5-api-라우팅-전략)
6. [백엔드 아키텍처](#6-백엔드-아키텍처)
7. [프론트엔드 UI 설계](#7-프론트엔드-ui-설계)
8. [마이그레이션 전략](#8-마이그레이션-전략)
9. [위험 요소 및 대응책](#9-위험-요소-및-대응책)
10. [구현 계획](#10-구현-계획)
11. [성능 및 확장성](#11-성능-및-확장성)

---

## 1. 현재 시스템 분석

### 1.1 핵심 컴포넌트 구조

```
현재 아키텍처 (단일 장비)
┌─────────────────────────────────────────────────────────────┐
│                        Flask Application                     │
├─────────────────────────────────────────────────────────────┤
│  app/__init__.py                                             │
│  ├─ modbus_client (전역 변수)                                │
│  │  └─ CIE_H14A_Client (단일 인스턴스)                       │
│  │     ├─ host: 192.168.10.105                              │
│  │     ├─ polling_thread (백그라운드)                        │
│  │     ├─ output_queue (명령 큐)                            │
│  │     └─ auto_off_timers (타이머 관리)                     │
│  └─ api_monitor_data (전역 딕셔너리)                         │
├─────────────────────────────────────────────────────────────┤
│  app/routes.py                                               │
│  ├─ /api/status              → modbus_client.get_status()   │
│  ├─ /api/output/<channel>    → modbus_client.write_output() │
│  ├─ /api/output/<channel>/toggle                            │
│  ├─ /api/events              → SSE 스트림                   │
│  ├─ /api/get_sensor          → DI 감지 콜백                 │
│  └─ /api/monitor             → 모니터링 정보                │
├─────────────────────────────────────────────────────────────┤
│  Frontend (Single Device UI)                                │
│  ├─ index.html               → 4채널 DI/DO 표시             │
│  ├─ main.js                  → SSE 수신, 버튼 제어          │
│  └─ style.css                → Glass Morphism 테마          │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
   192.168.10.105:502
   (CIE-H14A 장비 1대)
```

### 1.2 현재 시스템의 핵심 특징

**✅ 강점:**
1. **절대 안 죽는 시스템**: 큐 기반 비동기 아키텍처
2. **스레드 안전**: Lock을 통한 동기화
3. **자동 재연결**: 연결 끊김 시 자동 복구
4. **DI 감지 시스템**: GET 요청 자동 전송
5. **Auto-Off 타이머**: 출력 자동 꺼짐 기능
6. **재시도 메커니즘**: 실패 시 3회 재시도 (0.1초 간격)
7. **SSE 실시간 업데이트**: 200ms 주기, 변화 감지 시만 전송
8. **Rate Limiting**: IP 기반 요청 제한
9. **OWASP 보안 표준**: 입력 검증, XSS 방지, 보안 헤더

**⚠️ 단일 장비 한계:**
- 전역 변수 `modbus_client` 하나만 존재
- 모든 API 엔드포인트가 단일 장비 가정
- 설정 파일이 단일 장비 IP만 저장
- UI가 4채널(DI0-3, DO0-3)만 표시

---

## 2. 요구사항 정의

### 2.1 기능 요구사항

| 번호 | 요구사항 | 우선순위 | 세부 내용 |
|------|----------|----------|-----------|
| FR-01 | 4대 장비 동시 제어 | 필수 | 각 장비는 CIE-H14A (4채널 DI/DO) |
| FR-02 | 장비별 독립 동작 | 필수 | 한 장비 오류가 다른 장비에 영향 없음 |
| FR-03 | 장비별 DI 감지 | 필수 | 각 장비마다 독립적인 GET 요청 전송 |
| FR-04 | 통합 설정 파일 | 필수 | 하나의 파일에서 4대 장비 모두 설정 |
| FR-05 | 한 화면에 모든 장비 표시 | 필수 | 스크롤 없이 4대 장비 상태 확인 가능 |
| FR-06 | 장비별 ID 구분 | 필수 | API에서 장비 ID로 구분 (예: device1, device2) |
| FR-07 | 기존 보안 기능 유지 | 필수 | Rate limiting, 입력 검증 등 |
| FR-08 | 기존 기능 호환성 | 필수 | Auto-off, 재시도, SSE 모두 유지 |

### 2.2 비기능 요구사항

| 번호 | 요구사항 | 측정 기준 |
|------|----------|-----------|
| NFR-01 | 응답 시간 | API 응답 < 100ms (단일 장비 제어 시) |
| NFR-02 | 동시성 | 4대 장비 동시 제어 시 블로킹 없음 |
| NFR-03 | 안정성 | 한 장비 연결 끊김이 다른 장비에 영향 0% |
| NFR-04 | 메모리 효율성 | 4대 확장 시 메모리 사용량 < 500MB |
| NFR-05 | UI 반응성 | SSE 업데이트 지연 < 500ms |
| NFR-06 | 확장성 | 추후 8대까지 확장 가능한 구조 |

---

## 3. 아키텍처 설계

### 3.1 전체 시스템 아키텍처 (멀티 디바이스)

```
┌───────────────────────────────────────────────────────────────────────┐
│                        Flask Application                              │
├───────────────────────────────────────────────────────────────────────┤
│  app/__init__.py                                                      │
│  ├─ modbus_clients = {}  (딕셔너리)                                   │
│  │  ├─ 'device1': CIE_H14A_Client(host=192.168.10.101)               │
│  │  ├─ 'device2': CIE_H14A_Client(host=192.168.10.102)               │
│  │  ├─ 'device3': CIE_H14A_Client(host=192.168.10.103)               │
│  │  └─ 'device4': CIE_H14A_Client(host=192.168.10.104)               │
│  │                                                                     │
│  └─ api_monitor_data (각 장비별 통계)                                 │
│     ├─ 'device1': {history, total_requests, ...}                      │
│     ├─ 'device2': {...}                                               │
│     ├─ 'device3': {...}                                               │
│     └─ 'device4': {...}                                               │
├───────────────────────────────────────────────────────────────────────┤
│  app/routes.py (멀티 디바이스 API)                                    │
│  ├─ /api/status                      → 전체 장비 상태                │
│  ├─ /api/devices                     → 장비 목록                     │
│  ├─ /api/devices/<device_id>/status  → 특정 장비 상태               │
│  ├─ /api/devices/<device_id>/output/<channel>  → 장비별 출력 제어  │
│  ├─ /api/devices/<device_id>/output/<channel>/toggle                │
│  ├─ /api/events                      → 전체 장비 SSE 스트림          │
│  ├─ /api/devices/<device_id>/events  → 특정 장비 SSE                │
│  ├─ /api/get_sensor                  → DI 감지 콜백 (device_id 필수)│
│  └─ /api/monitor                     → 전체 모니터링 (장비별 통계)   │
├───────────────────────────────────────────────────────────────────────┤
│  Frontend (Multi-Device UI)                                          │
│  ├─ index.html                                                        │
│  │  ├─ Device 1: 4채널 DI/DO (카드 1)                               │
│  │  ├─ Device 2: 4채널 DI/DO (카드 2)                               │
│  │  ├─ Device 3: 4채널 DI/DO (카드 3)                               │
│  │  └─ Device 4: 4채널 DI/DO (카드 4)                               │
│  ├─ main.js                                                           │
│  │  ├─ Multi-device SSE 처리                                         │
│  │  └─ Device ID 파라미터 전송                                       │
│  └─ style.css (4-device Grid Layout)                                 │
└───────────────────────────────────────────────────────────────────────┘
         │           │           │           │
         ▼           ▼           ▼           ▼
    Device 1    Device 2    Device 3    Device 4
  10.105:502  10.106:502  10.107:502  10.108:502
```

### 3.2 클라이언트 관리 전략

**옵션 1: 딕셔너리 기반 (추천) ✅**

```python
# app/__init__.py
modbus_clients = {}  # device_id → CIE_H14A_Client

def init_modbus_clients(app: Flask) -> None:
    global modbus_clients

    devices_config = app.config['DEVICES']  # 설정 파일에서 로드

    for device_id, device_config in devices_config.items():
        client = CIE_H14A_Client(
            host=device_config['host'],
            port=device_config.get('port', 502),
            unit_id=device_config.get('unit_id', 1),
            timeout=device_config.get('timeout', 0.3),
            poll_interval=device_config.get('poll_interval', 0.5),
            auto_off_time=device_config.get('auto_off_time', 1.0),
            retry_count=device_config.get('retry_count', 3),
            retry_delay=device_config.get('retry_delay', 0.1),
            sensor_url=device_config.get('sensor_url'),
            sensor_device_id=device_id  # 장비 ID 전달
        )

        # 연결 시도
        if client.connect():
            app.logger.info(f"[{device_id}] Modbus 연결 성공: {device_config['host']}")
        else:
            app.logger.warning(f"[{device_id}] Modbus 초기 연결 실패 (자동 재연결 시도)")

        # 폴링 시작 (각 장비마다 독립적인 스레드)
        client.start_polling()

        modbus_clients[device_id] = client

    app.logger.info(f"총 {len(modbus_clients)}대 장비 초기화 완료")
```

**장점:**
- ✅ 장비 추가/제거 유연성 (8대, 16대로 확장 가능)
- ✅ 장비별 독립적인 설정 가능
- ✅ 코드 재사용성 높음
- ✅ 기존 `CIE_H14A_Client` 클래스 재사용

**옵션 2: 리스트 기반 (비추천) ❌**
```python
modbus_clients = [client1, client2, client3, client4]
```
- ❌ 인덱스 기반 접근 (가독성 낮음)
- ❌ 장비 식별 어려움

---

## 4. 설정 파일 스키마

### 4.1 새로운 `.env` 파일 구조

**현재 (단일 장비):**
```env
MODBUS_HOST=192.168.10.105
MODBUS_PORT=502
SENSOR_DEVICE_ID=HHI_DEVICE_001
```

**변경 (멀티 디바이스):**
```env
# Flask 설정
FLASK_ENV=production
SECRET_KEY=hyundai-heavy-industry-modbus-secret-key-2025
FLASK_HOST=0.0.0.0
FLASK_PORT=5000

# 전역 Modbus 기본값 (모든 장비에 적용)
MODBUS_DEFAULT_PORT=502
MODBUS_DEFAULT_UNIT_ID=1
MODBUS_DEFAULT_TIMEOUT=0.3
MODBUS_DEFAULT_POLL_INTERVAL=0.5
MODBUS_DEFAULT_AUTO_OFF_TIME=1.0
MODBUS_DEFAULT_RETRY_COUNT=3
MODBUS_DEFAULT_RETRY_DELAY=0.1

# 센서 URL (모든 장비 공통)
SENSOR_URL=http://localhost:5000/api/get_sensor

# 장비 1 설정
DEVICE1_ENABLED=true
DEVICE1_NAME=출입구 1번
DEVICE1_HOST=192.168.10.101
DEVICE1_PORT=502
DEVICE1_UNIT_ID=1
# 나머지는 기본값 사용

# 장비 2 설정
DEVICE2_ENABLED=true
DEVICE2_NAME=출입구 2번
DEVICE2_HOST=192.168.10.102
# 모두 기본값 사용

# 장비 3 설정
DEVICE3_ENABLED=true
DEVICE3_NAME=출입구 3번
DEVICE3_HOST=192.168.10.103

# 장비 4 설정
DEVICE4_ENABLED=true
DEVICE4_NAME=출입구 4번
DEVICE4_HOST=192.168.10.104

# 로깅 설정
LOG_LEVEL=INFO
```

### 4.2 Config 클래스 수정

**파일: `config/config.py`**

```python
import os
from dotenv import load_dotenv
from typing import Dict, Any

load_dotenv()

class Config:
    """기본 설정"""

    # Flask 설정
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    FLASK_ENV = os.getenv('FLASK_ENV', 'production')

    # Modbus 전역 기본값
    MODBUS_DEFAULT_PORT = int(os.getenv('MODBUS_DEFAULT_PORT', 502))
    MODBUS_DEFAULT_UNIT_ID = int(os.getenv('MODBUS_DEFAULT_UNIT_ID', 1))
    MODBUS_DEFAULT_TIMEOUT = float(os.getenv('MODBUS_DEFAULT_TIMEOUT', 0.3))
    MODBUS_DEFAULT_POLL_INTERVAL = float(os.getenv('MODBUS_DEFAULT_POLL_INTERVAL', 0.5))
    MODBUS_DEFAULT_AUTO_OFF_TIME = float(os.getenv('MODBUS_DEFAULT_AUTO_OFF_TIME', 1.0))
    MODBUS_DEFAULT_RETRY_COUNT = int(os.getenv('MODBUS_DEFAULT_RETRY_COUNT', 3))
    MODBUS_DEFAULT_RETRY_DELAY = float(os.getenv('MODBUS_DEFAULT_RETRY_DELAY', 0.1))

    # 센서 URL
    SENSOR_URL = os.getenv('SENSOR_URL')

    # 장비 설정 파싱
    DEVICES = {}

    @classmethod
    def init_devices_config(cls):
        """환경 변수에서 장비 설정 파싱"""
        devices = {}

        for i in range(1, 9):  # 최대 8대까지 지원
            device_id = f'device{i}'
            enabled_key = f'DEVICE{i}_ENABLED'

            # 장비가 활성화되어 있는지 확인
            if os.getenv(enabled_key, 'false').lower() != 'true':
                continue

            # 필수 항목: HOST
            host = os.getenv(f'DEVICE{i}_HOST')
            if not host:
                print(f"경고: DEVICE{i}_HOST가 설정되지 않음 - 장비 {i} 스킵")
                continue

            # 장비 설정 구성
            devices[device_id] = {
                'name': os.getenv(f'DEVICE{i}_NAME', f'Device {i}'),
                'host': host,
                'port': int(os.getenv(f'DEVICE{i}_PORT', cls.MODBUS_DEFAULT_PORT)),
                'unit_id': int(os.getenv(f'DEVICE{i}_UNIT_ID', cls.MODBUS_DEFAULT_UNIT_ID)),
                'timeout': float(os.getenv(f'DEVICE{i}_TIMEOUT', cls.MODBUS_DEFAULT_TIMEOUT)),
                'poll_interval': float(os.getenv(f'DEVICE{i}_POLL_INTERVAL', cls.MODBUS_DEFAULT_POLL_INTERVAL)),
                'auto_off_time': float(os.getenv(f'DEVICE{i}_AUTO_OFF_TIME', cls.MODBUS_DEFAULT_AUTO_OFF_TIME)),
                'retry_count': int(os.getenv(f'DEVICE{i}_RETRY_COUNT', cls.MODBUS_DEFAULT_RETRY_COUNT)),
                'retry_delay': float(os.getenv(f'DEVICE{i}_RETRY_DELAY', cls.MODBUS_DEFAULT_RETRY_DELAY)),
                'sensor_url': os.getenv(f'DEVICE{i}_SENSOR_URL', cls.SENSOR_URL)
            }

        cls.DEVICES = devices
        return devices

# 앱 시작 시 장비 설정 초기화
Config.init_devices_config()
```

### 4.3 설정 검증 로직

```python
def validate_devices_config(devices: Dict[str, Any]) -> bool:
    """장비 설정 유효성 검증"""
    if not devices:
        raise ValueError("활성화된 장비가 없습니다. 최소 1대 이상 설정해야 합니다.")

    for device_id, config in devices.items():
        # 필수 항목 확인
        if 'host' not in config or not config['host']:
            raise ValueError(f"{device_id}: HOST가 설정되지 않았습니다.")

        # IP 형식 검증 (간단한 정규식)
        import re
        ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if not re.match(ip_pattern, config['host']):
            raise ValueError(f"{device_id}: 잘못된 IP 형식 - {config['host']}")

        # 포트 범위 확인
        if not (1 <= config['port'] <= 65535):
            raise ValueError(f"{device_id}: 포트 번호가 범위를 벗어남 - {config['port']}")

    return True
```

---

## 5. API 라우팅 전략

### 5.1 API 엔드포인트 설계

#### 5.1.1 전체 시스템 API

| 엔드포인트 | 메서드 | 설명 | Rate Limit |
|-----------|--------|------|-----------|
| `/api/status` | GET | 전체 장비 상태 조회 | 60/분 |
| `/api/devices` | GET | 활성화된 장비 목록 | 30/분 |
| `/api/monitor` | GET | 전체 모니터링 통계 (장비별 집계) | 20/분 |
| `/api/events` | GET | 전체 장비 SSE 스트림 (멀티플렉싱) | - |

#### 5.1.2 장비별 API

| 엔드포인트 | 메서드 | 설명 | Rate Limit |
|-----------|--------|------|-----------|
| `/api/devices/<device_id>/status` | GET | 특정 장비 상태 | 60/분 |
| `/api/devices/<device_id>/output/<channel>` | POST | 특정 장비 출력 제어 | 120/분 |
| `/api/devices/<device_id>/output/<channel>/toggle` | POST | 특정 장비 출력 토글 | 120/분 |
| `/api/devices/<device_id>/events` | GET | 특정 장비 SSE 스트림 | - |
| `/api/devices/<device_id>/config` | GET | 특정 장비 설정 조회 | 10/분 |

#### 5.1.3 센서 콜백 API

| 엔드포인트 | 메서드 | 설명 | Rate Limit |
|-----------|--------|------|-----------|
| `/api/get_sensor?id=<device_id>&di_states=...` | GET | DI 감지 콜백 (device_id 필수) | 60/분 |

### 5.2 API 구현 예시

**파일: `app/routes.py`**

```python
from flask import Blueprint, jsonify, request, Response, current_app
from app import modbus_clients
from app.validators import validate_device_id, validate_channel

bp = Blueprint('api', __name__)

# ============================================================================
# 전체 시스템 API
# ============================================================================

@bp.route('/api/status')
@handle_errors
@rate_limit(max_requests=60, window=60)
def get_all_status():
    """
    전체 장비 상태 조회

    Returns:
        {
            "devices": {
                "device1": {
                    "connected": true,
                    "name": "출입구 1번",
                    "inputs": [false, false, false, false],
                    "outputs": [false, false, false, false],
                    "timestamp": 1234567890.123,
                    "di_detection": {...}
                },
                "device2": {...},
                ...
            },
            "summary": {
                "total_devices": 4,
                "connected_devices": 3,
                "disconnected_devices": 1
            }
        }
    """
    all_status = {}
    connected_count = 0

    for device_id, client in modbus_clients.items():
        status = client.get_status()
        status['name'] = current_app.config['DEVICES'][device_id]['name']
        all_status[device_id] = status

        if status['connected']:
            connected_count += 1

    return jsonify({
        'devices': all_status,
        'summary': {
            'total_devices': len(modbus_clients),
            'connected_devices': connected_count,
            'disconnected_devices': len(modbus_clients) - connected_count
        }
    })


@bp.route('/api/devices')
@handle_errors
@rate_limit(max_requests=30, window=60)
def get_devices_list():
    """
    활성화된 장비 목록 조회

    Returns:
        {
            "devices": [
                {
                    "id": "device1",
                    "name": "출입구 1번",
                    "host": "192.168.10.***",  # 마스킹
                    "connected": true
                },
                ...
            ]
        }
    """
    devices_list = []

    for device_id, client in modbus_clients.items():
        config = current_app.config['DEVICES'][device_id]

        # IP 마스킹 (프로덕션 환경)
        host = config['host']
        if current_app.config.get('FLASK_ENV') == 'production':
            host_parts = host.split('.')
            if len(host_parts) == 4:
                host_parts[-1] = '***'
                host = '.'.join(host_parts)

        devices_list.append({
            'id': device_id,
            'name': config['name'],
            'host': host,
            'connected': client.is_connected()
        })

    return jsonify({'devices': devices_list})


# ============================================================================
# 장비별 API
# ============================================================================

@bp.route('/api/devices/<device_id>/status')
@handle_errors
@rate_limit(max_requests=60, window=60)
def get_device_status(device_id):
    """특정 장비 상태 조회"""
    # 장비 ID 검증
    device_id = validate_device_id(device_id, list(modbus_clients.keys()))

    if device_id not in modbus_clients:
        return jsonify({'error': 'Device not found'}), 404

    client = modbus_clients[device_id]
    status = client.get_status()
    status['name'] = current_app.config['DEVICES'][device_id]['name']

    return jsonify(status)


@bp.route('/api/devices/<device_id>/output/<int:channel>', methods=['POST'])
@handle_errors
@rate_limit(max_requests=120, window=60)
def control_device_output(device_id, channel):
    """특정 장비 출력 제어"""
    # 장비 ID 검증
    device_id = validate_device_id(device_id, list(modbus_clients.keys()))

    if device_id not in modbus_clients:
        return jsonify({'error': 'Device not found'}), 404

    # 채널 번호 검증
    channel = validate_channel(channel)

    # 요청 본문 검증
    if not request.is_json:
        return jsonify({'error': 'Content-Type must be application/json'}), 415

    data = request.get_json()
    if data is None or 'state' not in data:
        return jsonify({'error': 'Missing required field: state'}), 400

    from app.validators import validate_boolean
    state = validate_boolean(data['state'])

    # 출력 제어
    client = modbus_clients[device_id]
    success = client.write_output(channel, state)

    if success:
        current_app.logger.info(
            f"[{device_id}] Output control: channel={channel}, state={state}, "
            f"client={request.remote_addr}"
        )
        return jsonify({
            'success': True,
            'device_id': device_id,
            'channel': channel,
            'state': state
        })
    else:
        return jsonify({
            'error': 'Output control failed',
            'device_id': device_id,
            'channel': channel
        }), 500


@bp.route('/api/devices/<device_id>/output/<int:channel>/toggle', methods=['POST'])
@handle_errors
@rate_limit(max_requests=120, window=60)
def toggle_device_output(device_id, channel):
    """특정 장비 출력 토글"""
    device_id = validate_device_id(device_id, list(modbus_clients.keys()))

    if device_id not in modbus_clients:
        return jsonify({'error': 'Device not found'}), 404

    channel = validate_channel(channel)

    client = modbus_clients[device_id]
    success, new_state = client.toggle_output(channel)

    if success:
        current_app.logger.info(
            f"[{device_id}] Output toggle: channel={channel}, new_state={new_state}, "
            f"client={request.remote_addr}"
        )
        return jsonify({
            'success': True,
            'device_id': device_id,
            'channel': channel,
            'state': new_state
        })
    else:
        return jsonify({
            'error': 'Output toggle failed',
            'device_id': device_id,
            'channel': channel
        }), 500


# ============================================================================
# SSE 스트림
# ============================================================================

@bp.route('/api/events')
@handle_errors
def sse_stream_all():
    """
    전체 장비 SSE 스트림 (멀티플렉싱)

    모든 장비의 상태를 하나의 스트림으로 전송
    """
    def generate():
        if not modbus_clients:
            yield f"data: {json.dumps({'error': 'No devices configured'})}\n\n"
            return

        # 초기 상태 전송
        all_status = {}
        for device_id, client in modbus_clients.items():
            all_status[device_id] = client.get_status()

        yield f"data: {json.dumps({'type': 'initial', 'devices': all_status})}\n\n"

        # 이전 상태 저장
        prev_all_status = {k: v.copy() for k, v in all_status.items()}

        # 주기적으로 상태 확인 및 전송
        while True:
            try:
                time.sleep(0.2)  # 200ms 간격

                # 모든 장비 상태 조회
                all_status = {}
                for device_id, client in modbus_clients.items():
                    all_status[device_id] = client.get_status()

                # 변화가 있는 장비만 전송 (효율성)
                changed_devices = {}
                for device_id, status in all_status.items():
                    prev_status = prev_all_status.get(device_id, {})

                    if (status.get('inputs') != prev_status.get('inputs') or
                        status.get('outputs') != prev_status.get('outputs') or
                        status.get('connected') != prev_status.get('connected') or
                        status.get('di_detection', {}) != prev_status.get('di_detection', {})):

                        changed_devices[device_id] = status

                # 변화가 있으면 전송
                if changed_devices:
                    yield f"data: {json.dumps({'type': 'update', 'devices': changed_devices})}\n\n"

                    # 이전 상태 업데이트
                    for device_id, status in changed_devices.items():
                        prev_all_status[device_id] = status.copy()

            except GeneratorExit:
                break
            except Exception as e:
                current_app.logger.error(f"SSE stream error: {e}")
                break

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'X-Content-Type-Options': 'nosniff',
            'Connection': 'keep-alive'
        }
    )


@bp.route('/api/devices/<device_id>/events')
@handle_errors
def sse_stream_device(device_id):
    """특정 장비 SSE 스트림"""
    device_id = validate_device_id(device_id, list(modbus_clients.keys()))

    if device_id not in modbus_clients:
        return jsonify({'error': 'Device not found'}), 404

    def generate():
        client = modbus_clients[device_id]

        # 초기 상태 전송
        status = client.get_status()
        yield f"data: {json.dumps(status)}\n\n"

        prev_status = status.copy()

        while True:
            try:
                time.sleep(0.2)

                status = client.get_status()

                if (status['inputs'] != prev_status['inputs'] or
                    status['outputs'] != prev_status['outputs'] or
                    status['connected'] != prev_status['connected'] or
                    status.get('di_detection', {}) != prev_status.get('di_detection', {})):

                    yield f"data: {json.dumps(status)}\n\n"
                    prev_status = status.copy()

            except GeneratorExit:
                break
            except Exception as e:
                current_app.logger.error(f"[{device_id}] SSE stream error: {e}")
                break

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'X-Content-Type-Options': 'nosniff',
            'Connection': 'keep-alive'
        }
    )


# ============================================================================
# 센서 콜백 API
# ============================================================================

@bp.route('/api/get_sensor')
@handle_errors
@rate_limit(max_requests=60, window=60)
def get_sensor():
    """
    센서 엔드포인트 (DI 감지 시 호출됨)

    Query Parameters:
        id: 장비 ID (필수)
        di_states: DI 상태 (예: "1,0,0,0")
    """
    # 장비 ID 검증
    device_id = request.args.get('id')
    if not device_id:
        return jsonify({'error': 'Missing required parameter: id'}), 400

    try:
        device_id = validate_device_id(device_id, list(modbus_clients.keys()))
    except ValidationError as e:
        return jsonify({'error': 'Invalid device ID', 'message': str(e)}), 400

    # DI 상태 검증
    di_states = request.args.get('di_states', '')
    if di_states:
        if not all(c in '0,1' for c in di_states):
            return jsonify({'error': 'Invalid DI states format'}), 400

    current_app.logger.info(
        f"[Sensor Endpoint] DI detection received - "
        f"Device ID: {device_id}, DI States: [{di_states}], "
        f"Client: {request.remote_addr}"
    )

    return jsonify({
        'success': True,
        'message': 'DI detection received',
        'device_id': device_id,
        'di_states': di_states,
        'timestamp': time.time()
    })
```

### 5.3 Validator 수정

**파일: `app/validators.py`**

```python
def validate_device_id(device_id: str, valid_devices: list) -> str:
    """
    장비 ID 검증

    Args:
        device_id: 검증할 장비 ID
        valid_devices: 유효한 장비 ID 목록

    Returns:
        str: 검증된 장비 ID

    Raises:
        ValidationError: 유효하지 않은 장비 ID
    """
    if not device_id:
        raise ValidationError("장비 ID가 비어있습니다")

    # 영숫자, 하이픈, 언더스코어만 허용
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', device_id):
        raise ValidationError(f"잘못된 장비 ID 형식: {device_id}")

    # 유효한 장비 목록에 있는지 확인
    if device_id not in valid_devices:
        raise ValidationError(f"존재하지 않는 장비 ID: {device_id}")

    return device_id
```

---

## 6. 백엔드 아키텍처

### 6.1 스레드 관리

**현재 (단일 장비):**
```
Flask App
 └─ ModbusPollingThread (1개)
     └─ 0.5초마다 DI/DO 읽기
```

**변경 후 (4대 장비):**
```
Flask App
 ├─ Device1_ModbusPollingThread
 │   └─ 0.5초마다 Device1 DI/DO 읽기
 ├─ Device2_ModbusPollingThread
 │   └─ 0.5초마다 Device2 DI/DO 읽기
 ├─ Device3_ModbusPollingThread
 │   └─ 0.5초마다 Device3 DI/DO 읽기
 └─ Device4_ModbusPollingThread
     └─ 0.5초마다 Device4 DI/DO 읽기
```

**총 스레드 수:**
- Flask 워커 스레드: 1개 (Gunicorn `--workers 1`)
- Modbus 폴링 스레드: 4개 (장비당 1개)
- **합계: 5개 스레드**

**스레드 안전성:**
- 각 `CIE_H14A_Client` 인스턴스는 독립적인 `threading.Lock` 보유
- 장비 간 데이터 공유 없음 → 데드락 위험 없음

### 6.2 메모리 사용량 추정

| 항목 | 단일 장비 | 4대 장비 | 증가율 |
|------|-----------|----------|--------|
| `CIE_H14A_Client` 인스턴스 | 1개 × ~50KB | 4개 × ~50KB | 4배 |
| 폴링 스레드 스택 | 1개 × ~1MB | 4개 × ~1MB | 4배 |
| 출력 명령 큐 (maxlen=100) | 100개 × ~24B | 400개 × ~24B | 4배 |
| API 모니터링 deque (maxlen=100) | 100개 × ~100B | 400개 × ~100B | 4배 |
| **총 예상 메모리** | **~2MB** | **~8MB** | 4배 |

**결론: 메모리 사용량은 선형 증가 (4배), 총 10MB 미만으로 매우 경량**

### 6.3 동시성 처리

**시나리오: 4대 장비 동시 출력 제어 요청**

```
클라이언트 → POST /api/devices/device1/output/0 {"state": true}
           → POST /api/devices/device2/output/1 {"state": true}
           → POST /api/devices/device3/output/2 {"state": true}
           → POST /api/devices/device4/output/3 {"state": true}
```

**처리 흐름:**
1. 각 요청이 Flask 워커 스레드에 의해 순차 처리 (Gunicorn `--workers 1`)
2. `client.write_output()` 호출 → 명령을 큐에 추가 (블로킹 없음, 즉시 반환)
3. 각 장비의 폴링 스레드가 독립적으로 큐에서 명령을 꺼내 Modbus 쓰기 실행

**응답 시간:**
- API 응답: < 10ms (큐 추가만 수행)
- Modbus 쓰기 완료: 최대 500ms (다음 폴링 사이클)

**병목 현상 없음:**
- 각 장비의 폴링 스레드가 독립 실행
- 한 장비의 Modbus 타임아웃이 다른 장비에 영향 없음

---

## 7. 프론트엔드 UI 설계

### 7.1 레이아웃 구조

**화면 구성 (데스크톱 기준):**

```
┌──────────────────────────────────────────────────────────────────┐
│  네비게이션 바                                                     │
│  [경우 로고] CIE-H14A Modbus 제어 시스템  [API 문서] [연결 상태]  │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│  API 모니터링 (전체 통합)                                         │
│  가동시간  총요청  성공률  1분요청  평균응답  API상태              │
└──────────────────────────────────────────────────────────────────┘
┌────────────────────────────┬─────────────────────────────────────┐
│  Device 1: 출입구 1번       │  Device 2: 출입구 2번                │
│  [연결: ●] IP: 10.101       │  [연결: ●] IP: 10.102               │
│  ┌──────────────────────┐   │  ┌──────────────────────┐          │
│  │ DI  [●][○][○][○]    │   │  │ DI  [○][○][○][○]    │          │
│  └──────────────────────┘   │  └──────────────────────┘          │
│  ┌──────────────────────┐   │  ┌──────────────────────┐          │
│  │ DO  [ON][OFF][OFF][OFF]│  │  │ DO  [OFF][OFF][OFF][OFF]│      │
│  └──────────────────────┘   │  └──────────────────────┘          │
│  DI 감지: 대기 중            │  DI 감지: 대기 중                   │
├────────────────────────────┼─────────────────────────────────────┤
│  Device 3: 출입구 3번       │  Device 4: 출입구 4번                │
│  [연결: ●] IP: 10.103       │  [연결: ●] IP: 10.104               │
│  ┌──────────────────────┐   │  ┌──────────────────────┐          │
│  │ DI  [○][○][○][○]    │   │  │ DI  [○][○][○][○]    │          │
│  └──────────────────────┘   │  └──────────────────────┘          │
│  ┌──────────────────────┐   │  ┌──────────────────────┐          │
│  │ DO  [OFF][OFF][OFF][OFF]│  │  │ DO  [OFF][OFF][OFF][OFF]│      │
│  └──────────────────────┘   │  └──────────────────────┘          │
│  DI 감지: 대기 중            │  DI 감지: 대기 중                   │
└────────────────────────────┴─────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│  시스템 로그 (전체 통합)                                           │
│  [14:32:10] [device1] DO 0: ON                                   │
│  [14:32:08] [device2] DI 감지 - GET 요청 전송                    │
│  [14:32:05] [device1] Modbus 연결 복구됨                         │
└──────────────────────────────────────────────────────────────────┘
```

**반응형 디자인 (모바일/태블릿):**
- 태블릿: 2열 레이아웃 (Device 1-2 / Device 3-4)
- 모바일: 1열 레이아웃 (세로 스크롤)

### 7.2 HTML 구조

**파일: `app/static/index.html`**

```html
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CIE-H14A Modbus 멀티 제어 시스템</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
    <link rel="stylesheet" href="css/style.css">
</head>
<body>
    <!-- 네비게이션 바 -->
    <nav class="navbar navbar-dark">
        <div class="container-fluid">
            <span class="navbar-brand mb-0 h1">
                <div class="logo-container">
                    <!-- 경우 로고 (CSS로 표시) -->
                </div>
                <i class="bi bi-cpu"></i> CIE-H14A Modbus 멀티 제어 시스템
            </span>
            <div class="d-flex align-items-center">
                <a href="/docs" class="btn btn-outline-light btn-sm me-2">
                    <i class="bi bi-book"></i> API 문서
                </a>
                <span id="connectionStatus" class="badge bg-secondary">
                    <i class="bi bi-circle-fill"></i> 연결 중...
                </span>
            </div>
        </div>
    </nav>

    <div class="container-fluid mt-4">
        <!-- 알림 영역 -->
        <div id="alertContainer"></div>

        <!-- API 모니터링 카드 (전체 통합) -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card border-success">
                    <div class="card-header bg-success text-white">
                        <h5 class="mb-0">
                            <i class="bi bi-activity"></i> API 모니터링 (전체 시스템)
                        </h5>
                    </div>
                    <div class="card-body">
                        <div class="row text-center">
                            <div class="col-6 col-md-2">
                                <small class="text-muted">가동 시간</small>
                                <div class="fs-5 fw-bold text-primary" id="monitorUptime">-</div>
                            </div>
                            <div class="col-6 col-md-2">
                                <small class="text-muted">활성 장비</small>
                                <div class="fs-5 fw-bold text-success" id="monitorActiveDevices">-</div>
                            </div>
                            <div class="col-6 col-md-2">
                                <small class="text-muted">총 요청</small>
                                <div class="fs-5 fw-bold" id="monitorTotal">-</div>
                            </div>
                            <div class="col-6 col-md-2">
                                <small class="text-muted">성공률</small>
                                <div class="fs-5 fw-bold text-success" id="monitorSuccess">-</div>
                            </div>
                            <div class="col-6 col-md-2">
                                <small class="text-muted">1분 요청</small>
                                <div class="fs-5 fw-bold text-info" id="monitorRecent">-</div>
                            </div>
                            <div class="col-6 col-md-2">
                                <small class="text-muted">평균 응답</small>
                                <div class="fs-5 fw-bold text-warning" id="monitorAvgTime">-</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 4대 장비 그리드 레이아웃 -->
        <div class="row mb-4" id="devicesGrid">
            <!-- 동적으로 생성됨 (JavaScript) -->
        </div>

        <!-- 시스템 로그 (전체 통합) -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header bg-secondary text-white">
                        <h5 class="mb-0">
                            <i class="bi bi-journal-text"></i> 시스템 로그 (전체)
                        </h5>
                    </div>
                    <div class="card-body">
                        <div id="systemLog" class="system-log"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="js/main.js"></script>
</body>
</html>
```

### 7.3 JavaScript 로직

**파일: `app/static/js/main.js`**

```javascript
/**
 * 멀티 디바이스 Modbus 제어 시스템 - 프론트엔드
 */

let eventSource = null;
let devicesData = {};  // 장비 데이터 캐시

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', async function() {
    console.log('멀티 디바이스 Modbus 제어 시스템 초기화 중...');

    // 장비 목록 로드
    await loadDevicesList();

    // UI 생성
    renderDevicesGrid();

    // SSE 연결 시작
    connectSSE();

    // 초기 상태 로드
    await loadAllStatus();

    // API 모니터링 시작
    startMonitoring();
    setInterval(startMonitoring, 5000);
});

/**
 * 장비 목록 로드
 */
async function loadDevicesList() {
    try {
        const response = await fetch('/api/devices');
        if (!response.ok) throw new Error('장비 목록 로드 실패');

        const data = await response.json();

        // 장비 데이터 초기화
        data.devices.forEach(device => {
            devicesData[device.id] = {
                id: device.id,
                name: device.name,
                host: device.host,
                connected: device.connected,
                inputs: [false, false, false, false],
                outputs: [false, false, false, false],
                di_detection: {}
            };
        });

        console.log(`${data.devices.length}대 장비 로드 완료`);
        addLog('success', `${data.devices.length}대 장비 초기화 완료`);

    } catch (error) {
        console.error('장비 목록 로드 오류:', error);
        showAlert('danger', '장비 목록을 로드할 수 없습니다.');
    }
}

/**
 * 장비 그리드 UI 렌더링
 */
function renderDevicesGrid() {
    const grid = document.getElementById('devicesGrid');
    grid.innerHTML = '';

    Object.values(devicesData).forEach(device => {
        const deviceCard = createDeviceCard(device);
        grid.appendChild(deviceCard);
    });
}

/**
 * 장비 카드 생성
 */
function createDeviceCard(device) {
    const col = document.createElement('div');
    col.className = 'col-12 col-lg-6 mb-4';

    col.innerHTML = `
        <div class="card device-card" id="device-card-${device.id}">
            <div class="card-header bg-primary text-white">
                <div class="d-flex justify-content-between align-items-center">
                    <h5 class="mb-0">
                        <i class="bi bi-hdd-network"></i> ${device.name}
                    </h5>
                    <div>
                        <span class="badge bg-light text-dark me-2">${device.host}</span>
                        <span class="badge bg-secondary" id="conn-${device.id}">
                            <i class="bi bi-circle-fill"></i> 연결 중...
                        </span>
                    </div>
                </div>
            </div>
            <div class="card-body">
                <!-- 디지털 입력 -->
                <div class="mb-3">
                    <h6><i class="bi bi-download"></i> 디지털 입력 (DI)</h6>
                    <div class="d-flex justify-content-around">
                        ${[0, 1, 2, 3].map(ch => `
                            <div class="input-indicator" id="di-${device.id}-${ch}">
                                <i class="bi bi-circle-fill led-off"></i>
                                <div class="mt-1"><strong>DI ${ch}</strong></div>
                                <div class="input-state">OFF</div>
                            </div>
                        `).join('')}
                    </div>
                </div>

                <!-- 디지털 출력 -->
                <div class="mb-3">
                    <h6><i class="bi bi-upload"></i> 디지털 출력 (DO)</h6>
                    <div class="d-flex justify-content-around">
                        ${[0, 1, 2, 3].map(ch => `
                            <div class="output-control">
                                <button class="btn btn-sm btn-outline-secondary output-btn"
                                        id="do-${device.id}-${ch}"
                                        onclick="toggleOutput('${device.id}', ${ch})">
                                    <i class="bi bi-power"></i>
                                    <div class="mt-1"><strong>DO ${ch}</strong></div>
                                    <div class="output-state">OFF</div>
                                </button>
                            </div>
                        `).join('')}
                    </div>
                </div>

                <!-- DI 감지 상태 -->
                <div class="alert alert-info mb-0" id="di-detect-${device.id}" style="display: none;">
                    <small>
                        <i class="bi bi-radar"></i> DI 감지:
                        <span class="badge bg-secondary" id="di-detect-badge-${device.id}">대기 중</span>
                    </small>
                </div>
            </div>
        </div>
    `;

    return col;
}

/**
 * 전체 상태 로드
 */
async function loadAllStatus() {
    try {
        const response = await fetch('/api/status');
        if (!response.ok) throw new Error('상태 로드 실패');

        const data = await response.json();

        // 각 장비 상태 업데이트
        Object.entries(data.devices).forEach(([deviceId, status]) => {
            updateDeviceUI(deviceId, status);
        });

        // 요약 정보 업데이트
        updateConnectionSummary(data.summary);

    } catch (error) {
        console.error('상태 로드 오류:', error);
        showAlert('danger', '시스템 상태를 로드할 수 없습니다.');
    }
}

/**
 * SSE 연결 (멀티 디바이스)
 */
function connectSSE() {
    if (eventSource) {
        eventSource.close();
    }

    console.log('SSE 연결 시작...');

    eventSource = new EventSource('/api/events');

    eventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);

            if (data.error) {
                console.error('SSE 오류:', data.error);
                return;
            }

            // 초기 상태 (type: 'initial')
            if (data.type === 'initial' && data.devices) {
                Object.entries(data.devices).forEach(([deviceId, status]) => {
                    updateDeviceUI(deviceId, status);
                });
            }

            // 업데이트 (type: 'update')
            else if (data.type === 'update' && data.devices) {
                Object.entries(data.devices).forEach(([deviceId, status]) => {
                    updateDeviceUI(deviceId, status);
                    addLog('info', `[${deviceId}] 상태 업데이트`);
                });
            }

        } catch (error) {
            console.error('SSE 데이터 파싱 오류:', error);
        }
    };

    eventSource.onopen = function() {
        console.log('SSE 연결 성공');
        addLog('success', 'SSE 연결 성공');
    };

    eventSource.onerror = function(error) {
        console.error('SSE 오류:', error);
        setTimeout(() => connectSSE(), 5000);  // 5초 후 재연결
    };
}

/**
 * 장비 UI 업데이트
 */
function updateDeviceUI(deviceId, status) {
    // 연결 상태
    const connBadge = document.getElementById(`conn-${deviceId}`);
    if (connBadge) {
        if (status.connected) {
            connBadge.className = 'badge bg-success';
            connBadge.innerHTML = '<i class="bi bi-circle-fill"></i> 연결됨';
        } else {
            connBadge.className = 'badge bg-danger';
            connBadge.innerHTML = '<i class="bi bi-circle-fill"></i> 연결 끊김';
        }
    }

    // 입력 상태
    if (status.inputs) {
        status.inputs.forEach((state, ch) => {
            updateInputIndicator(deviceId, ch, state);
        });
    }

    // 출력 상태
    if (status.outputs) {
        status.outputs.forEach((state, ch) => {
            updateOutputButton(deviceId, ch, state);
        });
    }

    // DI 감지 상태
    if (status.di_detection) {
        updateDIDetectionStatus(deviceId, status.di_detection);
    }

    // 캐시 업데이트
    devicesData[deviceId] = { ...devicesData[deviceId], ...status };
}

/**
 * 입력 인디케이터 업데이트
 */
function updateInputIndicator(deviceId, channel, state) {
    const indicator = document.getElementById(`di-${deviceId}-${channel}`);
    if (!indicator) return;

    const led = indicator.querySelector('i');
    const stateText = indicator.querySelector('.input-state');

    if (state) {
        led.classList.remove('led-off');
        led.classList.add('led-on');
        stateText.textContent = 'ON';
        stateText.classList.add('state-on');
    } else {
        led.classList.remove('led-on');
        led.classList.add('led-off');
        stateText.textContent = 'OFF';
        stateText.classList.remove('state-on');
    }
}

/**
 * 출력 버튼 업데이트
 */
function updateOutputButton(deviceId, channel, state) {
    const button = document.getElementById(`do-${deviceId}-${channel}`);
    if (!button) return;

    const stateText = button.querySelector('.output-state');

    if (state) {
        button.classList.add('btn-warning');
        button.classList.remove('btn-outline-secondary');
        stateText.textContent = 'ON';
    } else {
        button.classList.remove('btn-warning');
        button.classList.add('btn-outline-secondary');
        stateText.textContent = 'OFF';
    }
}

/**
 * DI 감지 상태 업데이트
 */
function updateDIDetectionStatus(deviceId, diDetection) {
    const container = document.getElementById(`di-detect-${deviceId}`);
    const badge = document.getElementById(`di-detect-badge-${deviceId}`);

    if (!diDetection.enabled) {
        container.style.display = 'none';
        return;
    }

    container.style.display = 'block';

    if (diDetection.di_triggered && diDetection.request_sent) {
        badge.className = 'badge bg-danger';
        badge.textContent = 'DI 감지 - 종료 대기';
    } else if (diDetection.di_triggered && !diDetection.request_sent) {
        badge.className = 'badge bg-warning';
        badge.textContent = '요청 전송 중...';
    } else {
        badge.className = 'badge bg-success';
        badge.textContent = 'DI 수신 대기';
    }
}

/**
 * 출력 토글
 */
async function toggleOutput(deviceId, channel) {
    const button = document.getElementById(`do-${deviceId}-${channel}`);
    if (!button || button.disabled) return;

    button.disabled = true;

    try {
        const response = await fetch(`/api/devices/${deviceId}/output/${channel}/toggle`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) throw new Error(`출력 토글 실패: ${response.status}`);

        const result = await response.json();

        if (result.success) {
            addLog('success', `[${deviceId}] DO ${channel}: ${result.state ? 'ON' : 'OFF'}`);
        } else {
            throw new Error(result.error || '알 수 없는 오류');
        }

    } catch (error) {
        console.error('출력 제어 오류:', error);
        addLog('error', `[${deviceId}] DO ${channel} 제어 실패: ${error.message}`);
        showAlert('danger', `[${deviceId}] 출력 ${channel} 제어에 실패했습니다`);
    } finally {
        setTimeout(() => {
            if (button) button.disabled = false;
        }, 100);
    }
}

/**
 * 연결 요약 업데이트
 */
function updateConnectionSummary(summary) {
    const statusBadge = document.getElementById('connectionStatus');

    if (summary.connected_devices === summary.total_devices) {
        statusBadge.className = 'badge bg-success';
        statusBadge.innerHTML = `<i class="bi bi-circle-fill"></i> 전체 연결됨 (${summary.total_devices}/${summary.total_devices})`;
    } else if (summary.connected_devices === 0) {
        statusBadge.className = 'badge bg-danger';
        statusBadge.innerHTML = `<i class="bi bi-circle-fill"></i> 전체 연결 끊김 (0/${summary.total_devices})`;
    } else {
        statusBadge.className = 'badge bg-warning';
        statusBadge.innerHTML = `<i class="bi bi-circle-fill"></i> 일부 연결됨 (${summary.connected_devices}/${summary.total_devices})`;
    }
}

/**
 * 로그 추가
 */
function addLog(level, message) {
    const logContainer = document.getElementById('systemLog');
    const timestamp = new Date().toLocaleTimeString('ko-KR');

    const logEntry = document.createElement('div');
    logEntry.className = `log-entry log-${level}`;
    logEntry.innerHTML = `
        <span class="log-timestamp">[${timestamp}]</span>
        <span>${message}</span>
    `;

    logContainer.insertBefore(logEntry, logContainer.firstChild);

    while (logContainer.children.length > 100) {
        logContainer.removeChild(logContainer.lastChild);
    }
}

/**
 * 알림 표시
 */
function showAlert(type, message) {
    const alertContainer = document.getElementById('alertContainer');

    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    alertContainer.appendChild(alertDiv);

    setTimeout(() => alertDiv.remove(), 5000);
}

/**
 * API 모니터링
 */
async function startMonitoring() {
    try {
        const response = await fetch('/api/monitor');
        if (!response.ok) throw new Error('모니터링 정보 로드 실패');

        const data = await response.json();

        // 가동 시간
        document.getElementById('monitorUptime').textContent = formatUptime(data.uptime);

        // 활성 장비 수
        const connectedDevices = Object.values(devicesData).filter(d => d.connected).length;
        document.getElementById('monitorActiveDevices').textContent =
            `${connectedDevices}/${Object.keys(devicesData).length}`;

        // 총 요청 수
        document.getElementById('monitorTotal').textContent = data.total_requests.toLocaleString();

        // 성공률
        document.getElementById('monitorSuccess').textContent = `${data.success_rate}%`;

        // 1분 요청 수
        document.getElementById('monitorRecent').textContent = data.recent_1min.requests;

        // 평균 응답 시간
        document.getElementById('monitorAvgTime').textContent =
            `${data.recent_1min.avg_duration_ms.toFixed(1)}ms`;

    } catch (error) {
        console.error('모니터링 오류:', error);
    }
}

/**
 * 가동 시간 포맷팅
 */
function formatUptime(seconds) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (days > 0) return `${days}일 ${hours}시간`;
    if (hours > 0) return `${hours}시간 ${minutes}분`;
    if (minutes > 0) return `${minutes}분`;
    return `${Math.floor(seconds)}초`;
}
```

### 7.4 CSS 스타일 (추가 사항)

**파일: `app/static/css/style.css`**

```css
/* 멀티 디바이스 카드 스타일 */
.device-card {
    border: 2px solid var(--glass-border);
    border-radius: 15px;
    background: var(--glass-bg);
    backdrop-filter: blur(10px);
    transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.device-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 8px 16px rgba(0, 255, 136, 0.3);
}

/* 입력 인디케이터 (작게) */
.input-indicator {
    display: inline-block;
    text-align: center;
    font-size: 0.9rem;
}

.input-indicator i {
    font-size: 1.5rem;
}

/* 출력 버튼 (작게) */
.output-btn {
    width: 100%;
    padding: 0.5rem;
    font-size: 0.9rem;
    border-radius: 10px;
    transition: all 0.3s ease;
}

.output-btn:hover {
    transform: scale(1.05);
}

/* 반응형 그리드 */
@media (max-width: 991px) {
    /* 태블릿: 1열 레이아웃 */
    .col-lg-6 {
        flex: 0 0 100%;
        max-width: 100%;
    }
}

@media (min-width: 1400px) {
    /* 대형 화면: 2열 레이아웃 유지 */
    .col-lg-6 {
        flex: 0 0 50%;
        max-width: 50%;
    }
}
```

---

## 8. 마이그레이션 전략

### 8.1 단계별 마이그레이션 계획

**Phase 1: 백엔드 멀티 디바이스 지원 (2일)**
1. `config/config.py` 수정 - 멀티 디바이스 설정 파싱
2. `app/__init__.py` 수정 - `modbus_clients` 딕셔너리 초기화
3. `app/routes.py` 수정 - 멀티 디바이스 API 추가
4. `app/validators.py` 수정 - `validate_device_id()` 추가
5. 테스트 코드 작성 및 실행

**Phase 2: 프론트엔드 멀티 디바이스 UI (2일)**
1. `index.html` 수정 - 그리드 레이아웃
2. `main.js` 수정 - 멀티 디바이스 SSE 처리
3. `style.css` 수정 - 반응형 디자인
4. 크로스 브라우저 테스트 (Chrome, Edge, Safari)

**Phase 3: 통합 테스트 및 최적화 (1일)**
1. 4대 장비 동시 연결 테스트
2. 부하 테스트 (동시 요청 100개)
3. 메모리 프로파일링
4. 로그 분석 및 최적화

**Phase 4: 문서화 및 배포 (1일)**
1. `README.md` 업데이트
2. `CLAUDE.md` 업데이트
3. `.env.example` 작성
4. Docker 이미지 재빌드 및 배포

**총 소요 시간: 6일 (1주)**

### 8.2 후방 호환성 (Backward Compatibility)

**옵션 1: 기존 API 유지 (비추천) ❌**
- 기존 `/api/output/<channel>` → 첫 번째 장비 (device1)에만 적용
- 문제: 혼란 초래, 명확하지 않음

**옵션 2: 기존 API 제거 및 마이그레이션 (추천) ✅**
- 기존 엔드포인트 모두 제거
- 새로운 `/api/devices/<device_id>/...` 구조로 전면 전환
- 장점: 명확한 API 구조, 유지보수 용이

**권장 사항:**
- 기존 시스템이 외부 의존성이 없다면 **옵션 2** 선택
- API 버전 관리 불필요 (내부 시스템)

### 8.3 데이터 마이그레이션

**설정 파일 마이그레이션:**

```bash
# 1. 기존 .env 백업
cp .env .env.backup

# 2. 새로운 .env 템플릿 작성
cat > .env << 'EOF'
FLASK_ENV=production
SECRET_KEY=hyundai-heavy-industry-modbus-secret-key-2025

# 전역 기본값
MODBUS_DEFAULT_PORT=502
MODBUS_DEFAULT_TIMEOUT=0.3
MODBUS_DEFAULT_POLL_INTERVAL=0.5
MODBUS_DEFAULT_AUTO_OFF_TIME=1.0

SENSOR_URL=http://localhost:5000/api/get_sensor

# 장비 1 (기존 192.168.10.105 → 10.101로 변경)
DEVICE1_ENABLED=true
DEVICE1_NAME=출입구 1번
DEVICE1_HOST=192.168.10.101
DEVICE1_PORT=502
DEVICE1_UNIT_ID=1

# 장비 2-4 추가
DEVICE2_ENABLED=true
DEVICE2_NAME=출입구 2번
DEVICE2_HOST=192.168.10.102

DEVICE3_ENABLED=true
DEVICE3_NAME=출입구 3번
DEVICE3_HOST=192.168.10.103

DEVICE4_ENABLED=true
DEVICE4_NAME=출입구 4번
DEVICE4_HOST=192.168.10.104

LOG_LEVEL=INFO
EOF

# 3. Docker 컨테이너 재시작
docker-compose down
docker-compose build
docker-compose up -d
```

---

## 9. 위험 요소 및 대응책

### 9.1 기술적 위험

| 위험 요소 | 발생 확률 | 영향도 | 대응책 |
|----------|----------|--------|--------|
| **R1: 스레드 과다 생성** | 중 | 중 | 최대 8대로 제한, 각 장비 1스레드만 |
| **R2: 메모리 부족** | 낮 | 중 | 메모리 프로파일링, maxlen=100으로 제한 |
| **R3: Modbus 타임아웃 증가** | 중 | 높 | 각 장비별 독립적인 재연결 로직 |
| **R4: SSE 연결 과부하** | 중 | 중 | 변화 감지 시에만 전송, 200ms 간격 |
| **R5: API Rate Limit 초과** | 낮 | 낮 | 장비별 독립적인 Rate Limit 카운터 |
| **R6: UI 렌더링 성능 저하** | 낮 | 낮 | Virtual DOM 사용 없이, 직접 DOM 업데이트 |

### 9.2 운영상 위험

| 위험 요소 | 발생 확률 | 영향도 | 대응책 |
|----------|----------|--------|--------|
| **R7: 장비 IP 충돌** | 중 | 높 | 네트워크 스캔 도구로 사전 확인 |
| **R8: 설정 파일 오류** | 높 | 높 | 설정 검증 로직 추가 (`validate_devices_config`) |
| **R9: 한 장비 장애가 전체 영향** | 낮 | 매우 높 | 장비별 독립적인 스레드/큐/타이머 |
| **R10: 동시 제어 시 충돌** | 낮 | 중 | 각 장비마다 독립적인 Lock |

### 9.3 성능 벤치마크

**테스트 시나리오:**
1. **단일 장비 제어 응답 시간**: < 50ms
2. **4대 장비 동시 제어**: < 100ms (병렬 처리)
3. **SSE 업데이트 지연**: < 500ms
4. **메모리 사용량**: < 200MB (4대 장비)
5. **CPU 사용률**: < 10% (유휴 상태), < 50% (부하 상태)

**부하 테스트 도구:**
```bash
# Apache Bench로 100개 동시 요청
ab -n 1000 -c 100 -p payload.json -T application/json \
   http://localhost:5000/api/devices/device1/output/0
```

---

## 10. 구현 계획

### 10.1 개발 일정 (6일)

| 일자 | 작업 내용 | 담당 | 산출물 |
|------|----------|------|--------|
| **Day 1** | 백엔드 설정 파싱 및 초기화 로직 | Backend | `config.py`, `__init__.py` |
| **Day 2** | 멀티 디바이스 API 구현 | Backend | `routes.py`, `validators.py` |
| **Day 3** | 프론트엔드 그리드 레이아웃 | Frontend | `index.html`, `style.css` |
| **Day 4** | 프론트엔드 SSE 및 제어 로직 | Frontend | `main.js` |
| **Day 5** | 통합 테스트 및 버그 수정 | Full-stack | 테스트 보고서 |
| **Day 6** | 문서화 및 배포 | DevOps | `README.md`, Docker 이미지 |

### 10.2 테스트 체크리스트

**단위 테스트 (Unit Tests):**
- [ ] `Config.init_devices_config()` - 4대 장비 파싱
- [ ] `validate_device_id()` - 유효한/무효한 장비 ID
- [ ] `CIE_H14A_Client` - 각 장비 독립 동작
- [ ] Rate Limiting - 장비별 독립적인 카운터

**통합 테스트 (Integration Tests):**
- [ ] 4대 장비 동시 연결
- [ ] 4대 장비 동시 출력 제어
- [ ] SSE 스트림 멀티플렉싱
- [ ] DI 감지 시 장비별 GET 요청

**UI 테스트:**
- [ ] 데스크톱 (1920x1080) - 2열 레이아웃
- [ ] 태블릿 (768x1024) - 2열 레이아웃
- [ ] 모바일 (375x667) - 1열 레이아웃
- [ ] 크로스 브라우저 (Chrome, Edge, Safari)

**성능 테스트:**
- [ ] 부하 테스트 - 1000 req/min
- [ ] 메모리 프로파일링 - < 200MB
- [ ] CPU 사용률 - < 50% (부하 시)
- [ ] SSE 지연 - < 500ms

**보안 테스트:**
- [ ] Rate Limiting - 120/분 초과 시 429 응답
- [ ] 입력 검증 - 잘못된 device_id 시 400 응답
- [ ] CSRF 방지 - POST 요청에 토큰 필요 (향후)
- [ ] SQL Injection 방지 - N/A (DB 미사용)

---

## 11. 성능 및 확장성

### 11.1 병목 현상 분석

**잠재적 병목 지점:**

1. **Flask 단일 워커**
   - 현재: Gunicorn `--workers 1` (Modbus 연결 충돌 방지)
   - 병목: 동시 요청 처리 제한
   - 해결책: 각 장비마다 독립적인 큐 사용 → 블로킹 없음

2. **Modbus TCP 타임아웃**
   - 현재: 0.3초 타임아웃
   - 병목: 한 장비 타임아웃 시 전체 지연?
   - 해결책: ✅ 각 장비 독립 스레드 → 영향 없음

3. **SSE 연결 과다**
   - 현재: 200ms 주기 폴링
   - 병목: 4대 장비 × 4채널 × 5Hz = 80 업데이트/초
   - 해결책: 변화 감지 시에만 전송 → 실제 10-20 업데이트/초

### 11.2 확장성 로드맵

**현재 → 4대 → 8대 → 16대**

| 항목 | 4대 | 8대 | 16대 |
|------|-----|-----|------|
| 폴링 스레드 | 4 | 8 | 16 |
| 메모리 사용량 | ~8MB | ~16MB | ~32MB |
| SSE 업데이트/초 | ~20 | ~40 | ~80 |
| API 응답 시간 | < 100ms | < 150ms | < 200ms |

**확장 시 고려 사항:**
- 16대 이상: SSE 스트림 분리 (장비별 별도 엔드포인트)
- 32대 이상: 데이터베이스 도입 (상태 캐싱)
- 64대 이상: 마이크로서비스 아키텍처 전환

### 11.3 최적화 기법

**이미 적용된 최적화:**
- ✅ 큐 기반 비동기 처리 (블로킹 없음)
- ✅ 변화 감지 시에만 SSE 전송
- ✅ deque(maxlen=100)으로 메모리 제한
- ✅ 스레드 안전 Lock (최소한의 범위)
- ✅ 재시도 메커니즘 (3회, 0.1초 간격)

**추가 최적화 가능:**
- 🔧 Redis 캐싱 (상태 공유)
- 🔧 WebSocket으로 SSE 대체 (양방향 통신)
- 🔧 gRPC로 Modbus 프록시 서버 분리

---

## 12. 결론 및 권장사항

### 12.1 핵심 요약

**✅ 실현 가능성: 매우 높음 (95%)**
- 기존 아키텍처가 멀티 디바이스 확장에 매우 유리
- `CIE_H14A_Client` 클래스 재사용 가능
- 큐 기반 비동기 아키텍처 → 장비 간 독립성 보장

**✅ 기술적 난이도: 중간 (5/10)**
- 백엔드: 딕셔너리 관리, API 라우팅 추가
- 프론트엔드: 그리드 레이아웃, SSE 멀티플렉싱
- 복잡한 알고리즘 불필요

**✅ 개발 기간: 6일 (1주)**
- 백엔드 2일, 프론트엔드 2일, 테스트 1일, 문서화 1일

**✅ 위험도: 낮음 (2/10)**
- 장비별 독립 동작 → 한 장비 장애가 전체에 영향 없음
- 메모리 사용량 선형 증가 (4배) → 여전히 경량 (< 10MB)
- 기존 보안 기능 모두 유지

### 12.2 최종 권장 사항

**1. 설정 파일 전략:**
- ✅ `.env` 파일에 `DEVICE1~4_HOST` 형식 사용
- ✅ 전역 기본값 + 장비별 오버라이드 패턴
- ✅ 설정 검증 로직 필수

**2. API 설계:**
- ✅ `/api/devices/<device_id>/...` 구조 채택
- ✅ 기존 단일 장비 API는 제거 (명확성)
- ✅ 전체 상태 API (`/api/status`) 추가

**3. UI 레이아웃:**
- ✅ 2×2 그리드 레이아웃 (데스크톱)
- ✅ 반응형 디자인 (모바일: 1열, 태블릿: 2열)
- ✅ 장비별 독립적인 카드 UI

**4. 구현 우선순위:**
- 1순위: 백엔드 멀티 디바이스 초기화
- 2순위: API 라우팅
- 3순위: 프론트엔드 그리드 레이아웃
- 4순위: SSE 멀티플렉싱

**5. 테스트 전략:**
- Phase 1: 단일 장비 테스트 (기존 기능 보존 확인)
- Phase 2: 2대 장비 테스트 (독립성 검증)
- Phase 3: 4대 장비 동시 부하 테스트
- Phase 4: 연결 끊김 시나리오 테스트

### 12.3 예상 산출물

**코드 파일:**
- `config/config.py` (수정)
- `app/__init__.py` (수정)
- `app/routes.py` (수정)
- `app/validators.py` (수정)
- `app/static/index.html` (수정)
- `app/static/js/main.js` (수정)
- `app/static/css/style.css` (수정)
- `.env` (수정)
- `.env.example` (신규)

**문서:**
- `README.md` (업데이트)
- `CLAUDE.md` (업데이트)
- `MULTI_DEVICE_MIGRATION_GUIDE.md` (신규)
- `API_REFERENCE.md` (업데이트)

**테스트 코드:**
- `tests/test_multi_device_routes.py` (신규)
- `tests/test_config_parsing.py` (신규)
- `tests/test_device_independence.py` (신규)

---

## 13. 다음 단계

**즉시 실행 가능한 액션 아이템:**

1. ✅ **이 분석 문서 검토 및 승인**
   - 사용자 피드백 수렴
   - 요구사항 재확인

2. 🔧 **개발 환경 준비**
   - Git 브랜치 생성: `feature/multi-device`
   - 로컬 테스트 환경 구성 (4대 시뮬레이터)

3. 🔧 **Phase 1 시작: 백엔드 설정 파싱**
   - `config/config.py` 수정
   - `.env.example` 작성
   - 단위 테스트 작성

4. 🔧 **마일스톤 설정**
   - M1: 백엔드 완료 (Day 2)
   - M2: 프론트엔드 완료 (Day 4)
   - M3: 통합 테스트 완료 (Day 5)
   - M4: 프로덕션 배포 (Day 6)

---

**문서 작성 완료. 사용자 검토 대기 중입니다.**

추가 질문이나 수정 요청이 있으시면 알려주세요!

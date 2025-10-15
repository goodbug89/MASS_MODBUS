# 멀티 디바이스 설정 가이드

**CIE-H14A Modbus TCP/IP 제어 시스템 - 4대 장비 확장**

작성일: 2025-10-15

---

## 📋 목차

1. [개요](#개요)
2. [사용자 결정사항](#사용자-결정사항)
3. [테스트 환경 구성](#테스트-환경-구성)
4. [설정 파일 작성](#설정-파일-작성)
5. [다음 단계](#다음-단계)

---

## 개요

1대의 CIE-H14A 장비를 제어하던 시스템을 **4대의 장비를 동시 제어**하도록 확장합니다.

**핵심 변경사항:**
- ✅ 장비 IP: 192.168.10.101~104 사용
- ✅ 장비 이름: Lane1, Lane2, Lane3, Lane4
- ✅ 개발 우선순위: 백엔드 먼저, 그 다음 프론트엔드
- ✅ 테스트 환경: 가상 시뮬레이터 or 실제 장비

---

## 사용자 결정사항

### 1. 장비 IP 주소 범위

**결정:** 192.168.10.101 ~ 192.168.10.104 사용 (기존 대로)

```
Device 1 (Lane1): 192.168.10.101:502
Device 2 (Lane2): 192.168.10.102:502
Device 3 (Lane3): 192.168.10.103:502
Device 4 (Lane4): 192.168.10.104:502
```

### 2. 장비 이름 규칙

**결정:** Lane1, Lane2, Lane3, Lane4 형식 사용

- ❌ "출입구 1번, 출입구 2번" → 너무 길고 가독성 낮음
- ✅ "Lane1, Lane2, Lane3, Lane4" → 간결하고 국제적

### 3. 개발 우선순위

**결정:** 백엔드 먼저 개발

**이유:**
- 백엔드가 안정적으로 동작해야 프론트엔드 테스트 가능
- API 스펙이 확정되어야 UI 개발 가능
- 통합 테스트를 위해 백엔드 우선 필요

**개발 순서:**
```
Phase 1: 백엔드 설정 파싱 (Day 1)
Phase 2: 백엔드 API 라우팅 (Day 2)
Phase 3: 백엔드 테스트 (Day 2)
Phase 4: 프론트엔드 UI (Day 3-4)
Phase 5: 통합 테스트 (Day 5)
Phase 6: 배포 (Day 6)
```

### 4. 테스트 환경 구성

**결정:** 가상 시뮬레이터 사용

**문제점:**
- pyModbusTCP의 서버 모듈이 Windows 환경에서 포트 바인딩 실패
- 복잡한 멀티 포트 바인딩 로직 필요

**해결책 (3가지 옵션):**

---

## 테스트 환경 구성

### 옵션 1: ModbusPal 시뮬레이터 사용 (추천) ✅

**ModbusPal**: Java 기반 무료 Modbus 시뮬레이터

**다운로드:**
- https://sourceforge.net/projects/modbuspal/
- 또는 https://github.com/zeelos/ModbusPal

**설정 방법:**

1. **ModbusPal 실행**
   ```bash
   java -jar ModbusPal.jar
   ```

2. **4개의 Slave 추가**
   - Slave 1: IP 127.0.0.1, Port 5020, Unit ID 1
   - Slave 2: IP 127.0.0.1, Port 5021, Unit ID 1
   - Slave 3: IP 127.0.0.1, Port 5022, Unit ID 1
   - Slave 4: IP 127.0.0.1, Port 5023, Unit ID 1

3. **각 Slave에 레지스터 추가**
   - **Discrete Inputs**: 주소 0-3 (DI0-DI3)
   - **Coils**: 주소 8-11 (DO0-DO3)

4. **시뮬레이터 시작**
   - "Start" 버튼 클릭

5. **.env 파일 수정**
   ```env
   DEVICE1_HOST=127.0.0.1
   DEVICE1_PORT=5020

   DEVICE2_HOST=127.0.0.1
   DEVICE2_PORT=5021

   DEVICE3_HOST=127.0.0.1
   DEVICE3_PORT=5022

   DEVICE4_HOST=127.0.0.1
   DEVICE4_PORT=5023
   ```

**장점:**
- GUI 제공, 직관적 사용
- 안정적인 Modbus 서버 구현
- 레지스터 값 실시간 모니터링 가능

**단점:**
- Java 런타임 필요
- GUI 프로그램 (백그라운드 실행 불가)

---

### 옵션 2: Diagslave 사용 (CLI, 상용)

**Diagslave**: 전문적인 Modbus 시뮬레이터 (14일 무료 평가판)

**다운로드:**
- https://www.modbusdriver.com/diagslave.html

**사용 방법:**
```bash
# 4개의 Diagslave 인스턴스 실행 (각각 다른 포트)
diagslave -m tcp -p 5020
diagslave -m tcp -p 5021
diagslave -m tcp -p 5022
diagslave -m tcp -p 5023
```

**장점:**
- CLI 기반, 자동화 가능
- 안정적이고 빠름
- 백그라운드 실행 가능

**단점:**
- 상용 소프트웨어 (평가판 14일)
- GUI 없음

---

### 옵션 3: 실제 CIE-H14A 장비 사용 (최종 테스트용)

**설정 방법:**

1. **네트워크 구성**
   - 장비 4대를 같은 네트워크에 연결
   - 각 장비에 고정 IP 할당:
     - 192.168.10.101
     - 192.168.10.102
     - 192.168.10.103
     - 192.168.10.104

2. **ezManager 도구로 장비 설정**
   - Modbus TCP 활성화
   - IP 주소 할당
   - Unit ID = 1 (모든 장비 동일)

3. **ping 테스트**
   ```bash
   ping 192.168.10.101
   ping 192.168.10.102
   ping 192.168.10.103
   ping 192.168.10.104
   ```

4. **.env 파일 수정**
   ```env
   DEVICE1_HOST=192.168.10.101
   DEVICE2_HOST=192.168.10.102
   DEVICE3_HOST=192.168.10.103
   DEVICE4_HOST=192.168.10.104
   ```

**장점:**
- 실제 하드웨어 테스트
- 최종 검증용으로 완벽

**단점:**
- 장비 4대 필요 (비용, 공간)
- 개발 초기 단계에서 사용 불편

---

## 설정 파일 작성

### 새로운 `.env` 파일 템플릿

```env
# Flask 설정
FLASK_ENV=production
SECRET_KEY=hyundai-heavy-industry-modbus-secret-key-2025
FLASK_HOST=0.0.0.0
FLASK_PORT=5000

# ==============================================================================
# 전역 Modbus 기본값 (모든 장비에 공통 적용)
# ==============================================================================
MODBUS_DEFAULT_PORT=502
MODBUS_DEFAULT_UNIT_ID=1
MODBUS_DEFAULT_TIMEOUT=0.3
MODBUS_DEFAULT_POLL_INTERVAL=0.5
MODBUS_DEFAULT_AUTO_OFF_TIME=1.0
MODBUS_DEFAULT_RETRY_COUNT=3
MODBUS_DEFAULT_RETRY_DELAY=0.1

# 센서 URL (DI 감지 시 호출할 URL)
SENSOR_URL=http://localhost:5000/api/get_sensor

# ==============================================================================
# 장비 1 설정 (Lane1)
# ==============================================================================
DEVICE1_ENABLED=true
DEVICE1_NAME=Lane1
DEVICE1_HOST=192.168.10.101
# 나머지는 기본값 사용 (PORT=502, UNIT_ID=1, TIMEOUT=0.3, ...)

# ==============================================================================
# 장비 2 설정 (Lane2)
# ==============================================================================
DEVICE2_ENABLED=true
DEVICE2_NAME=Lane2
DEVICE2_HOST=192.168.10.102

# ==============================================================================
# 장비 3 설정 (Lane3)
# ==============================================================================
DEVICE3_ENABLED=true
DEVICE3_NAME=Lane3
DEVICE3_HOST=192.168.10.103

# ==============================================================================
# 장비 4 설정 (Lane4)
# ==============================================================================
DEVICE4_ENABLED=true
DEVICE4_NAME=Lane4
DEVICE4_HOST=192.168.10.104

# ==============================================================================
# 고급 설정 (특정 장비만 다르게 설정하고 싶을 때)
# ==============================================================================
# DEVICE1_PORT=502
# DEVICE1_UNIT_ID=1
# DEVICE1_TIMEOUT=0.5
# DEVICE1_POLL_INTERVAL=0.3
# DEVICE1_AUTO_OFF_TIME=2.0
# DEVICE1_RETRY_COUNT=5
# DEVICE1_RETRY_DELAY=0.2
# DEVICE1_SENSOR_URL=http://192.168.10.100/sensor

# 로깅 설정
LOG_LEVEL=INFO
```

### 테스트용 `.env` 파일 (시뮬레이터)

```env
# Flask 설정
FLASK_ENV=development
SECRET_KEY=test-secret-key
FLASK_HOST=0.0.0.0
FLASK_PORT=5000

# 전역 기본값
MODBUS_DEFAULT_PORT=502
MODBUS_DEFAULT_UNIT_ID=1
MODBUS_DEFAULT_TIMEOUT=0.3
MODBUS_DEFAULT_POLL_INTERVAL=0.5
MODBUS_DEFAULT_AUTO_OFF_TIME=1.0
MODBUS_DEFAULT_RETRY_COUNT=3
MODBUS_DEFAULT_RETRY_DELAY=0.1

SENSOR_URL=http://localhost:5000/api/get_sensor

# 시뮬레이터 장비 설정 (로컬호스트, 다른 포트)
DEVICE1_ENABLED=true
DEVICE1_NAME=Lane1
DEVICE1_HOST=127.0.0.1
DEVICE1_PORT=5020

DEVICE2_ENABLED=true
DEVICE2_NAME=Lane2
DEVICE2_HOST=127.0.0.1
DEVICE2_PORT=5021

DEVICE3_ENABLED=true
DEVICE3_NAME=Lane3
DEVICE3_HOST=127.0.0.1
DEVICE3_PORT=5022

DEVICE4_ENABLED=true
DEVICE4_NAME=Lane4
DEVICE4_HOST=127.0.0.1
DEVICE4_PORT=5023

LOG_LEVEL=DEBUG
```

---

## 다음 단계

### Phase 1: 백엔드 설정 파싱 (Day 1)

**작업 목록:**

1. ✅ **분석 문서 작성 완료**
   - [MULTI_DEVICE_ARCHITECTURE_ANALYSIS.md](MULTI_DEVICE_ARCHITECTURE_ANALYSIS.md) 작성 완료
   - 아키텍처, API 설계, UI 레이아웃 모두 정의됨

2. ✅ **설정 가이드 작성 완료**
   - [MULTI_DEVICE_SETUP_GUIDE.md](MULTI_DEVICE_SETUP_GUIDE.md) (본 문서)

3. 🔧 **config/config.py 수정** (다음 작업)
   - `Config.init_devices_config()` 메서드 추가
   - 환경 변수에서 DEVICE1~4 파싱
   - 전역 기본값 + 장비별 오버라이드 로직

4. 🔧 **설정 검증 로직 추가**
   - IP 형식 검증
   - 포트 범위 검증 (1-65535)
   - 필수 필드 확인 (HOST)

5. 🔧 **단위 테스트 작성**
   - `tests/test_config_parsing.py` 작성
   - 정상 케이스, 에러 케이스 모두 테스트

**예상 소요 시간:** 4시간

---

### Phase 2: 백엔드 API 라우팅 (Day 2)

**작업 목록:**

1. 🔧 **app/__init__.py 수정**
   - `modbus_client` (단일) → `modbus_clients` (딕셔너리)
   - `init_modbus_clients()` 함수 작성
   - 각 장비마다 독립적인 폴링 스레드 시작

2. 🔧 **app/routes.py 수정**
   - 전체 시스템 API 추가:
     - `GET /api/status` → 전체 장비 상태
     - `GET /api/devices` → 장비 목록
   - 장비별 API 추가:
     - `GET /api/devices/<device_id>/status`
     - `POST /api/devices/<device_id>/output/<channel>`
     - `POST /api/devices/<device_id>/output/<channel>/toggle`
   - SSE 멀티플렉싱:
     - `GET /api/events` → 전체 장비 SSE

3. 🔧 **app/validators.py 수정**
   - `validate_device_id()` 함수 추가
   - 장비 ID 검증 로직

4. 🔧 **통합 테스트**
   - Postman 또는 curl로 API 테스트
   - 4대 장비 동시 제어 테스트

**예상 소요 시간:** 8시간

---

### Phase 3: 프론트엔드 UI (Day 3-4)

**작업 목록:**

1. 🔧 **app/static/index.html 수정**
   - 그리드 레이아웃 (2×2)
   - 장비 카드 컴포넌트
   - 반응형 디자인

2. 🔧 **app/static/js/main.js 수정**
   - 멀티 디바이스 SSE 처리
   - 장비별 상태 업데이트
   - 장비별 출력 제어

3. 🔧 **app/static/css/style.css 수정**
   - 장비 카드 스타일
   - 반응형 그리드

**예상 소요 시간:** 12시간

---

### Phase 4: 통합 테스트 및 배포 (Day 5-6)

**작업 목록:**

1. 🔧 **4대 장비 동시 연결 테스트**
2. 🔧 **부하 테스트 (100 req/min)**
3. 🔧 **메모리 프로파일링**
4. 🔧 **문서 업데이트**
   - README.md
   - CLAUDE.md
   - API_REFERENCE.md
5. 🔧 **Docker 이미지 재빌드 및 배포**

**예상 소요 시간:** 8시간

---

## 참고 자료

- **분석 문서**: [MULTI_DEVICE_ARCHITECTURE_ANALYSIS.md](MULTI_DEVICE_ARCHITECTURE_ANALYSIS.md)
- **현재 프로젝트 가이드**: [CLAUDE.md](CLAUDE.md)
- **보안 개선 사항**: [SECURITY_IMPROVEMENTS.md](SECURITY_IMPROVEMENTS.md)

---

## 질문 및 지원

추가 질문이나 수정 요청이 있으시면 언제든지 말씀해 주세요!

**다음 작업:**
```bash
# Phase 1 시작: 백엔드 설정 파싱
# config/config.py 파일 수정
```

준비되셨으면 바로 시작하겠습니다! 🚀

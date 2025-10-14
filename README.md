# CIE-H14A Modbus TCP/IP 제어 시스템

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/Flask-3.0-green.svg" alt="Flask">
  <img src="https://img.shields.io/badge/Docker-Ready-blue.svg" alt="Docker">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

CIE-H14A 4채널 원격 I/O 컨트롤러를 Modbus TCP/IP 프로토콜을 통해 웹에서 모니터링하고 제어하는 시스템입니다.

## 주요 기능

- 🔌 **4채널 디지털 입력 모니터링**: 실시간 입력 상태 표시
- ⚡ **4채널 디지털 출력 제어**: 웹 인터페이스를 통한 릴레이 제어
- 🔄 **실시간 업데이트**: Server-Sent Events를 통한 자동 상태 갱신
- 🎨 **반응형 디자인**: 모바일, 태블릿, 데스크톱 지원
- 🐳 **Docker 지원**: 간편한 배포 및 실행
- 🔧 **자동 재연결**: 연결 끊김 시 자동 재연결 시도

## 빠른 시작

### 사전 요구사항

- Docker & Docker Compose (권장)
- 또는 Python 3.11+ (로컬 개발 시)
- CIE-H14A 제어기 (네트워크 연결)

### Docker로 실행 (권장)

1. **환경 설정**
   ```bash
   cp .env.example .env
   # .env 파일을 편집하여 Modbus 설정 입력
   ```

2. **실행**
   ```bash
   docker-compose up -d
   ```

3. **접속**

   브라우저에서 `http://localhost:5000` 접속

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

`.env` 파일에서 다음 설정을 구성할 수 있습니다:

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `MODBUS_HOST` | CIE-H14A IP 주소 | 10.1.0.1 |
| `MODBUS_PORT` | Modbus TCP 포트 | 502 |
| `MODBUS_UNIT_ID` | Modbus Unit ID | 1 |
| `MODBUS_TIMEOUT` | 연결 타임아웃 (초) | 5.0 |
| `POLL_INTERVAL` | 폴링 간격 (초) | 0.5 |
| `FLASK_ENV` | Flask 환경 | production |
| `SECRET_KEY` | Flask 시크릿 키 | (변경 필요) |

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

### REST API 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/` | GET | 메인 웹 페이지 |
| `/health` | GET | 헬스 체크 |
| `/api/status` | GET | 전체 입출력 상태 조회 |
| `/api/output/<channel>` | POST | 출력 채널 제어 |
| `/api/output/<channel>/toggle` | POST | 출력 채널 토글 |
| `/api/events` | GET | SSE 스트림 |
| `/api/config` | GET | 현재 설정 조회 |

### 사용 예시

**출력 제어**
```bash
curl -X POST http://localhost:5000/api/output/0 \
  -H "Content-Type: application/json" \
  -d '{"state": true}'
```

**상태 조회**
```bash
curl http://localhost:5000/api/status
```

응답:
```json
{
  "connected": true,
  "inputs": [false, true, false, true],
  "outputs": [true, false, false, true],
  "timestamp": 1697186400.123
}
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

## 트러블슈팅

### Modbus 연결 실패

**문제**: `Modbus 연결 실패: 10.1.0.1:502`

**해결**:
1. CIE-H14A 전원 및 네트워크 연결 확인
2. IP 주소 핑 테스트: `ping 10.1.0.1`
3. 방화벽 포트 502 개방 확인
4. CIE-H14A에서 Modbus TCP 활성화 확인

### Docker 네트워크 이슈

**문제**: 컨테이너에서 호스트 네트워크 접근 불가

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

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 관련 링크

- [CIE-H14A 제품 페이지](https://www.sollae.co.kr/)
- [CIE-H14A 매뉴얼](https://www.sollae.co.kr/ko/download/pds_files/cieh14ako.pdf)
- [Modbus 프로토콜](https://modbus.org/)
- [Flask 문서](https://flask.palletsprojects.com/)
- [pyModbusTCP](https://github.com/sourceperl/pyModbusTCP)

---

**Made with ❤️ for Industrial IoT**

# 보안 개선사항 (Security Improvements)

이 문서는 OWASP Secure Coding 표준을 준수하기 위해 적용한 보안 개선사항을 설명합니다.

## 적용된 보안 조치

### 1. 입력 검증 (Input Validation)

**파일**: `app/validators.py`

- **문자열 Sanitization**: XSS 방지를 위한 HTML 태그 제거, 정규식 패턴 매칭
- **채널 번호 검증**: 0-3 범위 확인
- **Boolean 값 검증**: 타입 안전성 확보
- **URL 검증**: SSRF 방지를 위한 내부 IP 대역 차단
- **IP 주소 검증**: IPv4 형식 및 옥텟 범위 확인
- **포트 번호 검증**: 1-65535 범위 확인
- **JSON Payload 검증**: 필수 필드 및 허용되지 않은 필드 감지

**적용 예시**:
```python
from app.validators import validate_channel, validate_boolean

channel = validate_channel(request.args.get('channel'))
state = validate_boolean(request.json.get('state'))
```

### 2. Rate Limiting

**파일**: `app/routes.py`

- 클라이언트 IP 기반 요청 제한
- 엔드포인트별 차등 적용:
  - `/api/status`: 분당 60회
  - `/api/output/*`: 분당 120회
  - `/api/config`: 분당 10회
  - `/api/monitor`: 분당 20회

**효과**:
- DDoS 공격 완화
- 서버 리소스 보호
- 429 Too Many Requests 응답 반환

### 3. 보안 헤더 (Security Headers)

**파일**: `app/__init__.py`

적용된 헤더:
- `X-Content-Type-Options: nosniff` - MIME 타입 스니핑 방지
- `X-Frame-Options: DENY` - 클릭재킹 공격 방지
- `X-XSS-Protection: 1; mode=block` - XSS 필터 활성화
- `Strict-Transport-Security` - HTTPS 강제
- `Content-Security-Policy` - XSS 및 데이터 삽입 공격 방지
- Server 헤더 제거 - 서버 정보 은폐

### 4. 에러 처리 (Error Handling)

**개선사항**:
- 상세한 에러 정보는 로그에만 기록
- 클라이언트에는 일반적인 에러 메시지만 반환
- 스택 트레이스 노출 방지
- 404, 405, 429, 500 에러 핸들러 구현

**Before**:
```python
except Exception as e:
    return jsonify({'error': str(e)}), 500  # 위험: 상세 정보 노출
```

**After**:
```python
except Exception as e:
    current_app.logger.error(f"Error: {e}", exc_info=True)
    return jsonify({
        'error': 'Internal server error',
        'message': 'An unexpected error occurred'
    }), 500
```

### 5. 민감한 정보 보호

**구현**:
- 프로덕션 환경에서 IP 주소 마스킹 (마지막 옥텟 숨김)
- Sensor URL 경로 마스킹
- 로그에 민감한 데이터 기록 최소화

**예시**:
```python
# 개발: 192.168.10.105
# 프로덕션: 192.168.10.***
```

### 6. 환경 변수 관리

**개선사항**:
- `.env` 파일을 `.gitignore`에 추가
- `.env.example` 제공 (템플릿)
- SECRET_KEY 기본값 변경 필수 경고

**파일**:
- `.env.example`: 템플릿 파일 (버전 관리 대상)
- `.env`: 실제 설정 파일 (버전 관리 제외)

### 7. CORS 정책 강화

**개선사항**:
- 프로덕션 환경에서는 `ALLOWED_ORIGINS` 환경 변수로 특정 도메인만 허용
- 개발 환경에서만 `*` (모든 origin) 허용
- Preflight 요청 지원 (`Access-Control-Max-Age`)

### 8. Content-Type 검증

**구현**:
- POST 요청 시 `Content-Type: application/json` 강제
- 415 Unsupported Media Type 응답

### 9. 로깅 보안

**개선사항**:
- 클라이언트 IP 주소 기록
- 요청/응답 로깅 (민감한 데이터 제외)
- 비정상 접근 시도 로깅 (404, 429 등)
- 로그 레벨 설정 (환경 변수)

### 10. SSRF 방지

**구현**:
- URL 검증 시 내부 IP 대역 차단:
  - localhost (127.*)
  - 사설 IP (10.*, 192.168.*, 172.16-31.*)
  - 링크 로컬 (169.254.*)
- 개발 환경에서만 localhost 허용

### 11. SQL Injection 방지

**현재 상태**:
- 데이터베이스를 사용하지 않으므로 해당 없음
- 향후 데이터베이스 도입 시 ORM 사용 권장 (SQLAlchemy)

## 보안 테스트 체크리스트

### 입력 검증 테스트
- [ ] 잘못된 채널 번호 (음수, 범위 초과)
- [ ] 잘못된 데이터 타입 (문자열 → 숫자)
- [ ] XSS payload (`<script>alert('xss')</script>`)
- [ ] SQL Injection payload (`' OR '1'='1`)
- [ ] Path Traversal (`../../etc/passwd`)

### Rate Limiting 테스트
- [ ] 분당 100회 이상 요청
- [ ] 429 응답 확인
- [ ] `retry_after` 헤더 확인

### 보안 헤더 테스트
```bash
curl -I http://localhost:5000/api/status
```
확인 항목:
- [ ] X-Content-Type-Options: nosniff
- [ ] X-Frame-Options: DENY
- [ ] X-XSS-Protection: 1; mode=block
- [ ] Content-Security-Policy
- [ ] Server 헤더 없음

### 에러 처리 테스트
- [ ] 500 에러 발생 시 스택 트레이스 노출 없음
- [ ] 404 에러 메시지 일반화
- [ ] 로그 파일에만 상세 정보 기록

## 추가 권장 사항

### 프로덕션 환경

1. **HTTPS 사용**
   ```bash
   # Nginx 리버스 프록시 사용 권장
   server {
       listen 443 ssl;
       ssl_certificate /path/to/cert.pem;
       ssl_certificate_key /path/to/key.pem;
       location / {
           proxy_pass http://localhost:5000;
       }
   }
   ```

2. **방화벽 설정**
   - 필요한 포트만 개방 (5000, 502)
   - IP 화이트리스트 적용

3. **로그 모니터링**
   - 중앙 로그 수집 시스템 (ELK Stack, Grafana Loki)
   - 이상 패턴 탐지 알림

4. **정기 보안 업데이트**
   ```bash
   pip list --outdated
   pip install --upgrade <package>
   ```

5. **인증 시스템 도입**
   - JWT 또는 OAuth 2.0
   - API Key 기반 인증
   - Role-Based Access Control (RBAC)

### 코드 레벨

1. **의존성 보안 스캔**
   ```bash
   pip install safety
   safety check
   ```

2. **SAST (Static Application Security Testing)**
   ```bash
   pip install bandit
   bandit -r app/
   ```

3. **Secrets 스캔**
   ```bash
   pip install detect-secrets
   detect-secrets scan > .secrets.baseline
   ```

## 보안 연락처

보안 취약점을 발견한 경우:
- 이슈 트래커에 **공개하지 말 것**
- 담당자에게 직접 연락
- 책임있는 공개 (Responsible Disclosure) 준수

## 변경 이력

| 날짜 | 버전 | 변경사항 |
|-----|------|---------|
| 2025-10-15 | 1.1.0 | 보안 강화 (입력 검증, Rate Limiting, 보안 헤더) |
| 2025-10-14 | 1.0.0 | 초기 릴리스 |

## 참고 자료

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [OWASP Secure Coding Practices](https://owasp.org/www-project-secure-coding-practices-quick-reference-guide/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [Flask Security Best Practices](https://flask.palletsprojects.com/en/latest/security/)

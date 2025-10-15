# 로그 모니터링 명령어 (Windows PowerShell)

## 1. DI 감지 로그만 조회 (최근 로그)

### 방법 1: Select-String 사용 (가장 간단)
```powershell
docker-compose logs --tail=100 | Select-String "DI 감지|Sensor Endpoint"
```

### 방법 2: 더 많은 줄 조회
```powershell
docker-compose logs --tail=500 | Select-String "DI 감지|Sensor Endpoint"
```

### 방법 3: 모든 로그에서 검색
```powershell
docker-compose logs | Select-String "DI 감지|Sensor Endpoint"
```

---

## 2. 실시간 로그 모니터링

### 전체 로그 실시간 확인
```powershell
docker-compose logs -f
```

### 특정 키워드 강조 표시 (원라인)
```powershell
docker-compose logs -f 2>&1 | ForEach-Object { if ($_ -match "DI 감지|Sensor") { Write-Host $_ -ForegroundColor Cyan } else { Write-Host $_ } }
```

---

## 3. DI 감지 로그 색상 표시 (복사해서 사용)

```powershell
docker-compose logs --tail=200 | Select-String "DI 감지|Sensor Endpoint" | ForEach-Object {
    $line = $_.Line
    if ($line -match "DI 입력 감지") {
        Write-Host $line -ForegroundColor Green
    } elseif ($line -match "GET 요청 성공") {
        Write-Host $line -ForegroundColor Cyan
    } elseif ($line -match "모든 DI OFF") {
        Write-Host $line -ForegroundColor Yellow
    } elseif ($line -match "ERROR|실패") {
        Write-Host $line -ForegroundColor Red
    } else {
        Write-Host $line -ForegroundColor White
    }
}
```

---

## 4. 특정 시간대 로그 검색

```powershell
# 예: 04:58 시간대 로그
docker-compose logs --tail=1000 | Select-String "04:58"

# 예: 오늘 날짜 로그
docker-compose logs --tail=1000 | Select-String "2025-10-15"
```

---

## 5. 로그 파일로 저장

```powershell
# 전체 로그 저장
docker-compose logs > logs_full.txt

# DI 로그만 저장
docker-compose logs | Select-String "DI 감지|Sensor Endpoint" > logs_di.txt

# 타임스탬프 포함 저장
docker-compose logs --timestamps > "logs_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"
```

---

## 6. 현재 DI 상태 확인

```powershell
# JSON 포맷으로 조회
curl http://localhost:5000/api/status

# PowerShell 객체로 변환
$status = Invoke-RestMethod http://localhost:5000/api/status
$status.di_detection

# DI inputs만 조회
$status.inputs
```

---

## 7. 컨테이너 상태 확인

```powershell
# 컨테이너 실행 상태
docker-compose ps

# 컨테이너 리소스 사용량
docker stats modbus-controller --no-stream

# 컨테이너 재시작
docker-compose restart
```

---

## 8. 유용한 조합 명령어

### A. 최근 DI 이벤트 5개만 보기
```powershell
docker-compose logs --tail=500 | Select-String "DI 입력 감지" | Select-Object -Last 5
```

### B. GET 요청 성공 로그만 보기
```powershell
docker-compose logs --tail=200 | Select-String "GET 요청 성공"
```

### C. 에러 로그만 보기
```powershell
docker-compose logs --tail=200 | Select-String "ERROR|실패|Failed"
```

### D. 출력 제어 로그 보기
```powershell
docker-compose logs --tail=100 | Select-String "출력 제어|output"
```

---

## 9. 실시간 DI 모니터링 (권장)

아래 명령어를 PowerShell에 복사해서 실행하세요:

```powershell
Write-Host "=== DI Detection Monitor ===" -ForegroundColor Green
Write-Host "Monitoring started. Press Ctrl+C to exit.`n" -ForegroundColor Yellow

$lastLines = @{}
docker-compose logs -f --tail=10 2>&1 | ForEach-Object {
    $line = $_.ToString()

    # DI 관련 로그만 필터링
    if ($line -match "DI 감지|Sensor Endpoint|출력 제어") {
        # 중복 제거
        $hash = $line.GetHashCode()
        if (-not $lastLines.ContainsKey($hash)) {
            $lastLines[$hash] = $true

            # 색상 구분
            if ($line -match "DI 입력 감지") {
                Write-Host $line -ForegroundColor Green
            } elseif ($line -match "GET 요청 성공") {
                Write-Host $line -ForegroundColor Cyan
            } elseif ($line -match "모든 DI OFF") {
                Write-Host $line -ForegroundColor Yellow
            } elseif ($line -match "ERROR|실패") {
                Write-Host $line -ForegroundColor Red
            } elseif ($line -match "출력 제어") {
                Write-Host $line -ForegroundColor Magenta
            } else {
                Write-Host $line -ForegroundColor White
            }
        }
    }
}
```

---

## 10. 문제 해결

### 로그가 안 보일 때
```powershell
# 컨테이너 상태 확인
docker-compose ps

# 컨테이너가 실행 중이 아니면
docker-compose up -d

# 로그 레벨 확인 (.env 파일)
# LOG_LEVEL=INFO 로 설정되어 있는지 확인
```

### PowerShell 권한 오류
```powershell
# 현재 사용자에게 실행 권한 부여
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 한글 깨짐 현상
```powershell
# PowerShell 인코딩 설정
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# 그 후 다시 로그 조회
docker-compose logs --tail=100 | Select-String "DI"
```

---

## 빠른 참조

| 목적 | 명령어 |
|------|--------|
| 최근 DI 로그 | `docker-compose logs --tail=100 \| Select-String "DI 감지"` |
| 실시간 전체 로그 | `docker-compose logs -f` |
| 현재 DI 상태 | `curl http://localhost:5000/api/status` |
| 컨테이너 상태 | `docker-compose ps` |
| 컨테이너 재시작 | `docker-compose restart` |

---

**추천 사용법:**

1. **일상 모니터링**: `docker-compose logs --tail=100 | Select-String "DI 감지"`
2. **문제 발생 시**: `docker-compose logs --tail=500 | Select-String "ERROR|DI"`
3. **실시간 확인**: 위의 **9번 실시간 DI 모니터링** 명령어 사용


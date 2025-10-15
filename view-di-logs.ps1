# DI 감지 로그 조회 스크립트 (Windows PowerShell)
# 사용법: .\view-di-logs.ps1 [줄수]
# 예: .\view-di-logs.ps1 100

param(
    [int]$Lines = 200
)

Write-Host "=== 최근 DI 감지 로그 ($Lines 줄) ===" -ForegroundColor Green
Write-Host ""

# 최근 로그에서 DI 관련 항목만 필터링
docker-compose logs --tail=$Lines 2>&1 | ForEach-Object {
    $line = $_.ToString()

    if ($line -match "DI 감지|Sensor Endpoint") {
        # 시간 정보 포함 여부에 따라 색상 변경
        if ($line -match "\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}") {
            # DI 감지 상태에 따라 색상 구분
            if ($line -match "DI 입력 감지") {
                Write-Host $line -ForegroundColor Green
            }
            elseif ($line -match "GET 요청 성공") {
                Write-Host $line -ForegroundColor Cyan
            }
            elseif ($line -match "GET 요청 실패|ERROR") {
                Write-Host $line -ForegroundColor Red
            }
            elseif ($line -match "모든 DI OFF") {
                Write-Host $line -ForegroundColor Yellow
            }
            else {
                Write-Host $line -ForegroundColor White
            }
        }
    }
}

Write-Host ""
Write-Host "=== 로그 조회 완료 ===" -ForegroundColor Green

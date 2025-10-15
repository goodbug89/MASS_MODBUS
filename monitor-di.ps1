# DI 감지 로그 실시간 모니터링 스크립트 (Windows PowerShell)
# 사용법: .\monitor-di.ps1

Write-Host "=== DI 감지 로그 실시간 모니터링 ===" -ForegroundColor Green
Write-Host "종료하려면 Ctrl+C를 누르세요`n" -ForegroundColor Yellow

# 로그 스트림을 읽으면서 필터링
docker-compose logs -f 2>&1 | ForEach-Object {
    $line = $_.ToString()

    # DI 감지 관련 로그만 출력
    if ($line -match "DI 감지|Sensor Endpoint") {
        # 타임스탬프 추출
        if ($line -match "\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}") {
            Write-Host $line -ForegroundColor Cyan
        } else {
            Write-Host $line -ForegroundColor White
        }
    }
}

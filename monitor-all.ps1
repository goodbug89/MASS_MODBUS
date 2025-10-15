# 전체 로그 실시간 모니터링 스크립트 (Windows PowerShell)
# 사용법: .\monitor-all.ps1

Write-Host "=== 전체 로그 실시간 모니터링 ===" -ForegroundColor Green
Write-Host "종료하려면 Ctrl+C를 누르세요`n" -ForegroundColor Yellow

# 색상 설정
$colors = @{
    'ERROR'   = 'Red'
    'WARNING' = 'Yellow'
    'INFO'    = 'White'
    'DI 감지'  = 'Cyan'
    'Sensor'  = 'Green'
    'output'  = 'Magenta'
}

# 로그 스트림을 읽으면서 색상 적용
docker-compose logs -f 2>&1 | ForEach-Object {
    $line = $_.ToString()

    # 로그 레벨/키워드에 따라 색상 변경
    $color = 'White'
    foreach ($keyword in $colors.Keys) {
        if ($line -match $keyword) {
            $color = $colors[$keyword]
            break
        }
    }

    Write-Host $line -ForegroundColor $color
}

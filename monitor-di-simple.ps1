# DI Detection Log Monitor
Write-Host "=== DI Detection Log Monitor ===" -ForegroundColor Green
Write-Host "Press Ctrl+C to exit" -ForegroundColor Yellow
Write-Host ""

docker-compose logs -f 2>&1 | ForEach-Object {
    $line = $_.ToString()
    if ($line -match "DI 감지|Sensor Endpoint") {
        if ($line -match "\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}") {
            Write-Host $line -ForegroundColor Cyan
        } else {
            Write-Host $line -ForegroundColor White
        }
    }
}

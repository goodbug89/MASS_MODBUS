/**
 * CIE-H14A Modbus 멀티 제어 시스템 - 프론트엔드 JavaScript
 *
 * SSE(Server-Sent Events)를 통한 실시간 업데이트 처리
 * 멀티 디바이스 지원 - 최대 8대의 장비를 동시 제어
 */

// 전역 변수
let eventSource = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 10;
const RECONNECT_BASE_DELAY = 2000; // 2초
let reconnectTimeout = null;
let devicesData = {};  // 장비 데이터 캐시

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', async function() {
    console.log('CIE-H14A Modbus 멀티 제어 시스템 초기화 중...');

    // 장비 목록 로드
    await loadDevicesList();

    // 멀티 디바이스 UI 생성
    renderDevicesGrid();

    // SSE 연결 시작
    connectSSE();

    // 초기 상태 로드
    await loadAllStatus();

    // API 모니터링 시작 (5초마다)
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
 * 멀티 디바이스 그리드 UI 렌더링
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
    // 기존 재연결 타이머 취소
    if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
        reconnectTimeout = null;
    }

    // 기존 연결이 있으면 종료
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }

    console.log(`SSE 연결 시도 중... (시도 ${reconnectAttempts + 1}/${MAX_RECONNECT_ATTEMPTS})`);

    if (reconnectAttempts === 0) {
        addLog('info', 'SSE 연결 시작...');
    }

    try {
        eventSource = new EventSource('/api/events');

        // 메시지 수신
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
                    });
                }

                // 재연결 성공 - 카운터 초기화
                if (reconnectAttempts > 0) {
                    console.log('SSE 재연결 성공');
                    addLog('success', 'SSE 재연결 성공');
                    reconnectAttempts = 0;
                }

            } catch (error) {
                console.error('SSE 데이터 파싱 오류:', error);
            }
        };

        // 연결 성공
        eventSource.onopen = function() {
            console.log('SSE 연결 열림');
            if (reconnectAttempts === 0) {
                addLog('success', 'SSE 연결 성공');
            }
        };

        // 연결 오류 또는 종료
        eventSource.onerror = function(error) {
            console.error('SSE 오류 발생:', error);

            // 연결 닫기
            if (eventSource) {
                eventSource.close();
                eventSource = null;
            }

            // 재연결 시도
            if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                reconnectAttempts++;

                // 지수 백오프: 2초, 4초, 8초, 16초, 최대 32초
                const delay = Math.min(RECONNECT_BASE_DELAY * Math.pow(2, reconnectAttempts - 1), 32000);

                console.log(`${delay/1000}초 후 재연결 시도 (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);

                if (reconnectAttempts <= 3) {
                    addLog('warning', `${delay/1000}초 후 SSE 재연결 시도...`);
                }

                reconnectTimeout = setTimeout(connectSSE, delay);
            } else {
                console.error('최대 재연결 시도 횟수 초과');
                addLog('error', 'SSE 연결 실패: 최대 시도 횟수 초과');

                // 10초 후 재시도 카운터 리셋
                setTimeout(() => {
                    console.log('재연결 카운터 리셋');
                    reconnectAttempts = 0;
                    connectSSE();
                }, 10000);
            }
        };

    } catch (error) {
        console.error('SSE 연결 생성 오류:', error);

        // 재시도
        if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
            reconnectAttempts++;
            const delay = Math.min(RECONNECT_BASE_DELAY * Math.pow(2, reconnectAttempts - 1), 32000);
            reconnectTimeout = setTimeout(connectSSE, delay);
        }
    }
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
    if (devicesData[deviceId]) {
        devicesData[deviceId] = { ...devicesData[deviceId], ...status };
    }
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
    const statusText = document.getElementById('connectionText');

    if (summary.connected_devices === summary.total_devices) {
        statusBadge.className = 'badge bg-success';
        statusText.textContent = `전체 연결됨 (${summary.total_devices}/${summary.total_devices})`;
    } else if (summary.connected_devices === 0) {
        statusBadge.className = 'badge bg-danger';
        statusText.textContent = `전체 연결 끊김 (0/${summary.total_devices})`;
    } else {
        statusBadge.className = 'badge bg-warning';
        statusText.textContent = `일부 연결됨 (${summary.connected_devices}/${summary.total_devices})`;
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

        // 헬스 바 업데이트
        const healthBar = document.getElementById('monitorHealthBar');
        healthBar.style.width = `${data.success_rate}%`;

        // 마지막 체크 시간
        const lastCheck = new Date(data.last_check * 1000).toLocaleTimeString('ko-KR');
        document.getElementById('monitorLastCheck').textContent = lastCheck;

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

/**
 * 페이지 언로드 시 SSE 연결 종료
 */
window.addEventListener('beforeunload', function() {
    if (eventSource) {
        eventSource.close();
    }
});

/**
 * 페이지 가시성 변경 시 처리
 */
document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        if (eventSource) {
            eventSource.close();
        }
    } else {
        connectSSE();
        loadAllStatus();
    }
});

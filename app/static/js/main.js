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

// DI 감지 시간 추적 (각 디바이스별로 관리)
let diTimestamps = {}; // { 'device1': { 0: timestamp, 1: timestamp, ... } }

// DO3 자동제어 실행 여부 (중복 실행 방지)
let do3AutoTriggered = {}; // { 'device1': true/false }

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

    // 시뮬레이터 제어 초기화
    initSimulatorControl();
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
            // DI 타임스탬프 초기화
            diTimestamps[device.id] = { 0: null, 1: null, 2: null, 3: null };
            // DO3 자동제어 플래그 초기화
            do3AutoTriggered[device.id] = false;
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
                                <div class="input-time text-muted small" id="time-${device.id}-${ch}" style="min-height: 16px;">-</div>
                            </div>
                        `).join('')}
                    </div>
                </div>

                <!-- DI0-DI2 시간차 표시 -->
                <div class="mb-3">
                    <div class="alert alert-info mb-0 py-2" role="alert">
                        <div class="d-flex justify-content-between align-items-center">
                            <span><i class="bi bi-clock"></i> <strong>DI0-DI2 시간차:</strong></span>
                            <span class="badge bg-primary" id="timedelta-${device.id}" style="font-size: 0.9rem;">-</span>
                        </div>
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
                        <br>
                        <span class="text-muted" id="di-detect-url-${device.id}" style="font-size: 0.85em; word-break: break-all;"></span>
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
    const timeText = document.getElementById(`time-${deviceId}-${channel}`);

    // 이전 상태 확인 (엣지 트리거 방식)
    const previousState = devicesData[deviceId]?.inputs?.[channel] || false;

    if (state) {
        led.classList.remove('led-off');
        led.classList.add('led-on');
        stateText.textContent = 'ON';
        stateText.classList.add('state-on');

        // OFF → ON 전환 시 타임스탬프 기록
        if (!previousState) {
            const now = Date.now();
            if (!diTimestamps[deviceId]) {
                diTimestamps[deviceId] = {};
            }
            diTimestamps[deviceId][channel] = now;

            // 시간 표시
            const timeStr = new Date(now).toLocaleTimeString('ko-KR', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                fractionalSecondDigits: 3
            });
            if (timeText) {
                timeText.textContent = timeStr;
                timeText.classList.add('text-success');
            }

            // DI0-DI2 시간차 계산 (DI0 또는 DI2가 감지되었을 때)
            if (channel === 0 || channel === 2) {
                updateTimeDelta(deviceId);
            }
        }
    } else {
        led.classList.remove('led-on');
        led.classList.add('led-off');
        stateText.textContent = 'OFF';
        stateText.classList.remove('state-on');

        // DI0 또는 DI2가 OFF가 되면 타임스탬프 및 자동제어 플래그 리셋
        if (channel === 0 || channel === 2) {
            if (previousState && !state) {
                // ON → OFF 전환 시
                if (diTimestamps[deviceId]) {
                    diTimestamps[deviceId][channel] = null;
                }
                // 두 센서 모두 OFF가 되면 자동제어 플래그 리셋
                const di0Off = !devicesData[deviceId]?.inputs?.[0];
                const di2Off = !devicesData[deviceId]?.inputs?.[2];
                if (di0Off && di2Off) {
                    do3AutoTriggered[deviceId] = false;
                }
            }
        }
    }
}

/**
 * DI0-DI2 시간차 계산 및 표시
 */
function updateTimeDelta(deviceId) {
    const timeDeltaBadge = document.getElementById(`timedelta-${deviceId}`);
    if (!timeDeltaBadge) return;

    const di0Time = diTimestamps[deviceId]?.[0];
    const di2Time = diTimestamps[deviceId]?.[2];

    if (di0Time && di2Time) {
        // 시간차 계산 (밀리초)
        const deltaMs = Math.abs(di2Time - di0Time);

        // 표시 형식 선택
        let displayText = '';
        if (deltaMs < 1000) {
            // 1초 미만: 밀리초 표시
            displayText = `${deltaMs.toFixed(0)} ms`;
        } else {
            // 1초 이상: 초 단위 표시
            displayText = `${(deltaMs / 1000).toFixed(3)} 초`;
        }

        timeDeltaBadge.textContent = displayText;

        // 시간차에 따라 배지 색상 변경
        timeDeltaBadge.classList.remove('bg-primary', 'bg-success', 'bg-warning', 'bg-danger');
        if (deltaMs < 500) {
            timeDeltaBadge.classList.add('bg-success'); // 500ms 미만: 녹색
        } else if (deltaMs < 1000) {
            timeDeltaBadge.classList.add('bg-primary'); // 1초 미만: 파랑
        } else if (deltaMs < 1500) {
            timeDeltaBadge.classList.add('bg-warning'); // 1.5초 미만: 노랑
        } else {
            timeDeltaBadge.classList.add('bg-danger'); // 1.5초 이상: 빨강
        }

        // ⚡ 자동 제어: 1.5초 이내 감지 시 DO3를 0.5초간 켜기 (중복 실행 방지)
        if (deltaMs < 1500 && !do3AutoTriggered[deviceId]) {
            do3AutoTriggered[deviceId] = true;
            triggerDO3Pulse(deviceId, deltaMs);
        }
    } else if (di0Time || di2Time) {
        // 하나만 감지됨
        const detectedCh = di0Time ? 'DI0' : 'DI2';
        timeDeltaBadge.textContent = `${detectedCh}만 감지됨`;
        timeDeltaBadge.classList.remove('bg-primary', 'bg-success', 'bg-warning', 'bg-danger');
        timeDeltaBadge.classList.add('bg-secondary');
    } else {
        // 아직 감지 안됨
        timeDeltaBadge.textContent = '-';
        timeDeltaBadge.classList.remove('bg-success', 'bg-warning', 'bg-danger', 'bg-secondary');
        timeDeltaBadge.classList.add('bg-primary');
    }
}

/**
 * DO3 펄스 제어 (0.5초간 켜기)
 * DI0-DI2 시간차가 1.5초 이내일 때 자동 실행
 */
async function triggerDO3Pulse(deviceId, deltaMs) {
    try {
        console.log(`[자동제어] ${deviceId} - DI0-DI2 시간차 ${deltaMs}ms → DO3 펄스 시작`);

        // DO3 켜기 (channel 3)
        const onResponse = await fetch(`/api/devices/${deviceId}/output/3`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ state: true })
        });

        if (!onResponse.ok) {
            throw new Error('DO3 ON 실패');
        }

        addLog('success', `[${deviceId}] 자동제어: DO3 ON (시간차 ${deltaMs}ms)`);

        // 0.5초 대기
        await new Promise(resolve => setTimeout(resolve, 500));

        // DO3 끄기
        const offResponse = await fetch(`/api/devices/${deviceId}/output/3`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ state: false })
        });

        if (!offResponse.ok) {
            throw new Error('DO3 OFF 실패');
        }

        console.log(`[자동제어] ${deviceId} - DO3 펄스 완료`);
        addLog('info', `[${deviceId}] 자동제어: DO3 OFF (0.5초 펄스 완료)`);

    } catch (error) {
        console.error(`[자동제어] ${deviceId} DO3 펄스 오류:`, error);
        addLog('danger', `[${deviceId}] 자동제어 오류: ${error.message}`);
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
    const urlDisplay = document.getElementById(`di-detect-url-${deviceId}`);

    if (!diDetection.enabled) {
        container.style.display = 'none';
        return;
    }

    container.style.display = 'block';

    // URL 표시 (파라미터 포함 전체 URL)
    if (diDetection.di_triggered && diDetection.request_sent && diDetection.sensor_url && diDetection.device_id) {
        // 실제 전송된 DI 상태 기반으로 파라미터 생성
        const diStates = diDetection.di_states || [false, false, false, false];
        const timestamp = Date.now(); // 밀리초 단위 타임스탬프
        const params = new URLSearchParams({
            id: diDetection.device_id,
            di_states: diStates.map(s => s ? '1' : '0').join(','),
            time: timestamp
        });
        const fullUrl = `${diDetection.sensor_url}?${params.toString()}`;
        urlDisplay.textContent = `URL: ${fullUrl}`;
    } else {
        urlDisplay.textContent = '';
    }

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

// 전역 스코프에 노출 (onclick 속성에서 접근 가능하도록)
window.toggleOutput = toggleOutput;

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

// ==============================================================================
// 시뮬레이터 제어 기능
// ==============================================================================

/**
 * 시뮬레이터 제어 초기화
 */
function initSimulatorControl() {
    // 버튼 이벤트 리스너
    document.getElementById('btnSimulatorStart')?.addEventListener('click', startSimulator);
    document.getElementById('btnSimulatorStop')?.addEventListener('click', stopSimulator);
    document.getElementById('btnSimulatorRestart')?.addEventListener('click', restartSimulator);
    document.getElementById('btnSimulatorRefresh')?.addEventListener('click', checkSimulatorStatus);

    // 초기 상태 확인
    checkSimulatorStatus();

    // 10초마다 자동 상태 확인
    setInterval(checkSimulatorStatus, 10000);
}

/**
 * 시뮬레이터 상태 확인
 */
async function checkSimulatorStatus() {
    try {
        const response = await fetch('/api/simulator/status');
        const data = await response.json();

        const statusBadge = document.getElementById('simulatorStatus');
        const statusText = document.getElementById('simulatorStatusText');

        if (data.running) {
            statusBadge.className = 'badge bg-success';
            statusText.textContent = '실행 중';
        } else {
            statusBadge.className = 'badge bg-secondary';
            statusText.textContent = '중지됨';
        }

        console.log('Simulator status:', data);
    } catch (error) {
        console.error('시뮬레이터 상태 확인 실패:', error);
        const statusBadge = document.getElementById('simulatorStatus');
        const statusText = document.getElementById('simulatorStatusText');
        statusBadge.className = 'badge bg-danger';
        statusText.textContent = '오류';
    }
}

/**
 * 시뮬레이터 시작
 */
async function startSimulator() {
    const btn = document.getElementById('btnSimulatorStart');
    btn.disabled = true;
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i> 시작 중...';

    try {
        // API 키 가져오기 (meta 태그에서 또는 환경 변수)
        const apiKey = document.querySelector('meta[name="api-key"]')?.content;
        const headers = {
            'Content-Type': 'application/json'
        };

        // API 키가 있으면 헤더에 추가
        if (apiKey) {
            headers['X-API-Key'] = apiKey;
        }

        const response = await fetch('/api/simulator/start', {
            method: 'POST',
            headers: headers
        });

        const data = await response.json();

        if (response.status === 401 || response.status === 403) {
            showSimulatorMessage('인증 실패: ' + (data.message || 'API 키가 필요합니다'), 'danger');
            return;
        }

        if (data.success) {
            showSimulatorMessage('시뮬레이터가 성공적으로 시작되었습니다.', 'success');
            setTimeout(checkSimulatorStatus, 2000);
        } else {
            showSimulatorMessage('시뮬레이터 시작 실패: ' + (data.message || '알 수 없는 오류'), 'danger');
        }
    } catch (error) {
        console.error('시뮬레이터 시작 오류:', error);
        showSimulatorMessage('시뮬레이터 시작 중 오류가 발생했습니다.', 'danger');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-play-fill"></i> 시작';
    }
}

/**
 * 시뮬레이터 중지
 */
async function stopSimulator() {
    const btn = document.getElementById('btnSimulatorStop');
    btn.disabled = true;
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i> 중지 중...';

    try {
        const apiKey = document.querySelector('meta[name="api-key"]')?.content;
        const headers = {
            'Content-Type': 'application/json'
        };

        if (apiKey) {
            headers['X-API-Key'] = apiKey;
        }

        const response = await fetch('/api/simulator/stop', {
            method: 'POST',
            headers: headers
        });

        const data = await response.json();

        if (response.status === 401 || response.status === 403) {
            showSimulatorMessage('인증 실패: ' + (data.message || 'API 키가 필요합니다'), 'danger');
            return;
        }

        if (data.success) {
            showSimulatorMessage('시뮬레이터가 성공적으로 중지되었습니다.', 'warning');
            setTimeout(checkSimulatorStatus, 2000);
        } else {
            showSimulatorMessage('시뮬레이터 중지 실패: ' + (data.message || '알 수 없는 오류'), 'danger');
        }
    } catch (error) {
        console.error('시뮬레이터 중지 오류:', error);
        showSimulatorMessage('시뮬레이터 중지 중 오류가 발생했습니다.', 'danger');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-stop-fill"></i> 중지';
    }
}

/**
 * 시뮬레이터 재시작
 */
async function restartSimulator() {
    const btn = document.getElementById('btnSimulatorRestart');
    btn.disabled = true;
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i> 재시작 중...';

    try {
        const apiKey = document.querySelector('meta[name="api-key"]')?.content;
        const headers = {
            'Content-Type': 'application/json'
        };

        if (apiKey) {
            headers['X-API-Key'] = apiKey;
        }

        const response = await fetch('/api/simulator/restart', {
            method: 'POST',
            headers: headers
        });

        const data = await response.json();

        if (response.status === 401 || response.status === 403) {
            showSimulatorMessage('인증 실패: ' + (data.message || 'API 키가 필요합니다'), 'danger');
            return;
        }

        if (data.success) {
            showSimulatorMessage('시뮬레이터가 성공적으로 재시작되었습니다.', 'info');
            setTimeout(checkSimulatorStatus, 3000);
        } else {
            showSimulatorMessage('시뮬레이터 재시작 실패: ' + (data.message || '알 수 없는 오류'), 'danger');
        }
    } catch (error) {
        console.error('시뮬레이터 재시작 오류:', error);
        showSimulatorMessage('시뮬레이터 재시작 중 오류가 발생했습니다.', 'danger');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> 재시작';
    }
}

/**
 * 시뮬레이터 메시지 표시
 */
function showSimulatorMessage(message, type = 'info') {
    const messageDiv = document.getElementById('simulatorMessage');
    const messageText = document.getElementById('simulatorMessageText');
    const alertDiv = messageDiv.querySelector('.alert');

    messageText.textContent = message;
    alertDiv.className = `alert alert-${type} mb-0`;
    messageDiv.style.display = 'block';

    // 5초 후 자동 숨김
    setTimeout(() => {
        messageDiv.style.display = 'none';
    }, 5000);
}

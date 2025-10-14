/**
 * CIE-H14A Modbus 제어 시스템 - 프론트엔드 JavaScript
 *
 * SSE(Server-Sent Events)를 통한 실시간 업데이트 처리
 * 출력 제어 및 UI 업데이트 관리
 */

// 전역 변수
let eventSource = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 10;
const RECONNECT_BASE_DELAY = 2000; // 2초
let reconnectTimeout = null;

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    console.log('CIE-H14A Modbus 제어 시스템 초기화 중...');

    // 모든 버튼 활성화 (초기화)
    enableAllButtons();

    // 설정 정보 로드
    loadConfig();

    // SSE 연결 시작
    connectSSE();

    // 초기 상태 로드
    loadStatus();

    // API 모니터링 시작 (5초마다)
    startMonitoring();
    setInterval(startMonitoring, 5000);
});

/**
 * 모든 출력 버튼 활성화
 */
function enableAllButtons() {
    for (let i = 0; i < 4; i++) {
        const button = document.getElementById(`output${i}`);
        if (button) {
            button.disabled = false;
            console.log(`DO${i} 버튼 활성화`);
        }
    }
}

/**
 * 모든 입출력 초기화 (연결 끊김 시)
 */
function resetAllIO() {
    console.log('모든 입출력 초기화 시작');

    // 모든 DI를 OFF로 표시
    for (let i = 0; i < 4; i++) {
        updateInputIndicator(i, false);
    }

    // 모든 DO 버튼 비활성화 및 OFF로 표시
    for (let i = 0; i < 4; i++) {
        const button = document.getElementById(`output${i}`);
        if (button) {
            button.disabled = true;  // 버튼 비활성화
            const stateText = button.querySelector('.output-state');

            // OFF 스타일로 변경
            button.classList.remove('active', 'btn-warning');
            button.classList.add('btn-outline-secondary');
            if (stateText) {
                stateText.textContent = 'OFF';
            }

            console.log(`DO${i} 초기화: OFF, 비활성화`);
        }
    }

    console.log('모든 입출력 초기화 완료');
}

/**
 * 설정 정보 로드
 */
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        if (!response.ok) {
            throw new Error('설정 정보 로드 실패');
        }

        const config = await response.json();

        // 설정 정보 표시
        document.getElementById('configHost').textContent = config.modbus_host;
        document.getElementById('configPort').textContent = config.modbus_port;
        document.getElementById('configUnitId').textContent = config.modbus_unit_id;

        addLog('info', '설정 정보 로드 완료');
    } catch (error) {
        console.error('설정 정보 로드 오류:', error);
        showAlert('danger', '설정 정보를 로드할 수 없습니다.');
    }
}

/**
 * 초기 상태 로드
 */
async function loadStatus() {
    try {
        const response = await fetch('/api/status');
        if (!response.ok) {
            throw new Error('상태 로드 실패');
        }

        const status = await response.json();
        updateUI(status);
        addLog('success', '초기 상태 로드 완료');
    } catch (error) {
        console.error('상태 로드 오류:', error);
        showAlert('danger', '초기 상태를 로드할 수 없습니다.');
    }
}

/**
 * SSE 연결
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

    // 첫 연결 시에만 로그 표시
    if (reconnectAttempts === 0) {
        addLog('info', 'SSE 연결 시작...');
        updateConnectionStatus('connecting');
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

                // UI 업데이트
                updateUI(data);

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

                // 처음 몇 번만 로그 표시
                if (reconnectAttempts <= 3) {
                    addLog('warning', `${delay/1000}초 후 SSE 재연결 시도...`);
                }

                updateConnectionStatus('connecting');

                reconnectTimeout = setTimeout(connectSSE, delay);
            } else {
                console.error('최대 재연결 시도 횟수 초과');
                addLog('error', 'SSE 연결 실패: 최대 시도 횟수 초과');
                updateConnectionStatus('disconnected');

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

// 이전 연결 상태 추적
let previousConnectionState = null;

/**
 * UI 업데이트
 */
function updateUI(status) {
    const currentConnectionState = status.connected;

    // 연결 상태 업데이트
    updateConnectionStatus(currentConnectionState ? 'connected' : 'disconnected');

    // 연결이 끊어진 경우 모든 입출력 초기화
    if (!currentConnectionState) {
        console.log('Modbus 연결 끊김 - UI 초기화');
        resetAllIO();

        // 최초 연결 끊김 시에만 알림 표시
        if (previousConnectionState !== false) {
            addLog('warning', 'Modbus 연결 끊김 - 모든 입출력 초기화됨');
            showAlert('warning', 'Modbus 연결이 끊어졌습니다. 모든 출력 제어가 비활성화됩니다.');
        }

        previousConnectionState = false;
        return;
    }

    // 연결이 복구된 경우
    if (previousConnectionState === false && currentConnectionState) {
        console.log('Modbus 연결 복구 - 버튼 활성화');
        enableAllButtons();
        addLog('success', 'Modbus 연결 복구됨');
        showAlert('success', 'Modbus 연결이 복구되었습니다. 출력 제어가 가능합니다.');
    }

    previousConnectionState = currentConnectionState;

    // 입력 상태 업데이트
    if (status.inputs) {
        status.inputs.forEach((state, index) => {
            updateInputIndicator(index, state);
        });
    }

    // 출력 상태 업데이트
    if (status.outputs) {
        status.outputs.forEach((state, index) => {
            updateOutputButton(index, state);
        });
    }

    // 마지막 업데이트 시간
    if (status.timestamp) {
        const date = new Date(status.timestamp * 1000);
        document.getElementById('lastUpdate').textContent = date.toLocaleTimeString('ko-KR');
    }
}

/**
 * 연결 상태 업데이트
 */
function updateConnectionStatus(status) {
    const statusBadge = document.getElementById('connectionStatus');

    // 모든 상태 클래스 제거
    statusBadge.classList.remove('status-connected', 'status-disconnected', 'status-connecting');

    switch(status) {
        case 'connected':
            statusBadge.classList.add('status-connected');
            statusBadge.innerHTML = '<i class="bi bi-circle-fill status-indicator"></i> 연결됨';
            break;
        case 'disconnected':
            statusBadge.classList.add('status-disconnected');
            statusBadge.innerHTML = '<i class="bi bi-circle-fill status-indicator"></i> 연결 끊김';
            break;
        case 'connecting':
            statusBadge.classList.add('status-connecting');
            statusBadge.innerHTML = '<i class="bi bi-circle-fill status-indicator"></i> 연결 중...';
            break;
    }
}

/**
 * 입력 인디케이터 업데이트
 */
function updateInputIndicator(channel, state) {
    const indicator = document.getElementById(`input${channel}`);
    if (!indicator) return;

    const led = indicator.querySelector('i');
    const stateText = indicator.querySelector('.input-state');

    if (state) {
        led.classList.remove('led-off');
        led.classList.add('led-on');
        stateText.textContent = 'ON';
        stateText.classList.remove('state-off');
        stateText.classList.add('state-on');
    } else {
        led.classList.remove('led-on');
        led.classList.add('led-off');
        stateText.textContent = 'OFF';
        stateText.classList.remove('state-on');
        stateText.classList.add('state-off');
    }
}

/**
 * 출력 버튼 업데이트
 */
function updateOutputButton(channel, state) {
    const button = document.getElementById(`output${channel}`);
    if (!button) return;

    const stateText = button.querySelector('.output-state');

    if (state) {
        button.classList.add('active');
        button.classList.remove('btn-outline-secondary');
        button.classList.add('btn-warning');
        stateText.textContent = 'ON';
    } else {
        button.classList.remove('active');
        button.classList.remove('btn-warning');
        button.classList.add('btn-outline-secondary');
        stateText.textContent = 'OFF';
    }
}

/**
 * 출력 토글
 */
async function toggleOutput(channel) {
    console.log(`toggleOutput 호출: 채널 ${channel}`);

    const button = document.getElementById(`output${channel}`);
    if (!button) {
        console.error(`버튼을 찾을 수 없음: output${channel}`);
        return;
    }

    // 이미 비활성화되어 있으면 리턴 (연결 끊김 상태)
    if (button.disabled) {
        console.log('버튼이 비활성화 상태 - 연결 끊김');
        showAlert('warning', 'Modbus 연결이 끊어져 있습니다. 출력 제어가 불가능합니다.');
        return;
    }

    // 버튼 비활성화 (중복 클릭 방지)
    button.disabled = true;
    console.log('버튼 비활성화');

    try {
        console.log(`API 요청 시작: /api/output/${channel}/toggle`);
        const response = await fetch(`/api/output/${channel}/toggle`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        console.log(`API 응답: ${response.status}`);

        if (!response.ok) {
            throw new Error(`출력 토글 실패: ${response.status}`);
        }

        const result = await response.json();
        console.log('API 결과:', result);

        if (result.success) {
            addLog('success', `DO ${channel}: ${result.state ? 'ON' : 'OFF'}`);
            console.log(`DO ${channel} 제어 성공: ${result.state ? 'ON' : 'OFF'}`);
            // UI는 SSE를 통해 자동으로 업데이트됨
        } else {
            throw new Error(result.error || '알 수 없는 오류');
        }

    } catch (error) {
        console.error('출력 제어 오류:', error);
        addLog('error', `DO ${channel} 제어 실패: ${error.message}`);
        showAlert('danger', `출력 ${channel} 제어에 실패했습니다: ${error.message}`);
    } finally {
        // 버튼 다시 활성화
        console.log('버튼 재활성화 예약 (100ms 후)');
        setTimeout(() => {
            if (button) {
                button.disabled = false;
                console.log('버튼 재활성화 완료');
            }
        }, 100);
    }
}

/**
 * 알림 표시
 */
function showAlert(type, message) {
    const alertContainer = document.getElementById('alertContainer');

    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show fade-in`;
    alertDiv.role = 'alert';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    alertContainer.appendChild(alertDiv);

    // 5초 후 자동 제거
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

/**
 * 시스템 로그 추가
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

    // 로그를 맨 위에 추가
    logContainer.insertBefore(logEntry, logContainer.firstChild);

    // 로그가 50개 이상이면 오래된 것 제거
    while (logContainer.children.length > 50) {
        logContainer.removeChild(logContainer.lastChild);
    }
}

/**
 * API 모니터링 시작
 */
async function startMonitoring() {
    try {
        const response = await fetch('/api/monitor');
        if (!response.ok) {
            throw new Error('모니터링 정보 로드 실패');
        }

        const data = await response.json();
        updateMonitoringUI(data);

    } catch (error) {
        console.error('모니터링 오류:', error);
        // 모니터링 실패는 UI에 표시만 하고 에러는 띄우지 않음
        updateMonitoringUI(null);
    }
}

/**
 * 모니터링 UI 업데이트
 */
function updateMonitoringUI(data) {
    if (!data) {
        // 데이터 로드 실패
        document.getElementById('monitorStatus').innerHTML = '<i class="bi bi-circle-fill text-danger"></i>';
        document.getElementById('monitorHealthBar').style.width = '0%';
        document.getElementById('monitorHealthBar').classList.remove('bg-success');
        document.getElementById('monitorHealthBar').classList.add('bg-danger');
        return;
    }

    // 가동 시간 포맷팅
    const uptime = formatUptime(data.uptime);
    document.getElementById('monitorUptime').textContent = uptime;

    // 총 요청 수
    document.getElementById('monitorTotal').textContent = data.total_requests.toLocaleString();

    // 성공률
    const successRate = data.success_rate;
    document.getElementById('monitorSuccess').textContent = `${successRate}%`;

    // 1분 요청 수
    document.getElementById('monitorRecent').textContent = data.recent_1min.requests;

    // 평균 응답 시간
    const avgTime = data.recent_1min.avg_duration_ms;
    document.getElementById('monitorAvgTime').textContent = `${avgTime.toFixed(1)}ms`;

    // API 상태 (응답시간 기반)
    let statusIcon, statusColor, healthPercent;
    if (avgTime < 50) {
        statusIcon = 'bi-circle-fill text-success';
        statusColor = 'success';
        healthPercent = 100;
    } else if (avgTime < 200) {
        statusIcon = 'bi-circle-fill text-warning';
        statusColor = 'warning';
        healthPercent = 80;
    } else {
        statusIcon = 'bi-circle-fill text-danger';
        statusColor = 'danger';
        healthPercent = 50;
    }

    document.getElementById('monitorStatus').innerHTML = `<i class="bi ${statusIcon}"></i>`;

    // 헬스 바 업데이트
    const healthBar = document.getElementById('monitorHealthBar');
    healthBar.style.width = `${successRate}%`;
    healthBar.classList.remove('bg-success', 'bg-warning', 'bg-danger');
    healthBar.classList.add(`bg-${statusColor}`);

    // 마지막 체크 시간
    const lastCheck = new Date(data.last_check * 1000).toLocaleTimeString('ko-KR');
    document.getElementById('monitorLastCheck').textContent = lastCheck;
}

/**
 * 가동 시간 포맷팅
 */
function formatUptime(seconds) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (days > 0) {
        return `${days}일 ${hours}시간`;
    } else if (hours > 0) {
        return `${hours}시간 ${minutes}분`;
    } else if (minutes > 0) {
        return `${minutes}분`;
    } else {
        return `${Math.floor(seconds)}초`;
    }
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
        // 페이지가 숨겨지면 SSE 연결 종료
        if (eventSource) {
            eventSource.close();
        }
    } else {
        // 페이지가 다시 보이면 SSE 재연결
        connectSSE();
        loadStatus();
    }
});

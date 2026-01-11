/**
 * UWB 이륜차 하이패스 모니터링 시스템
 *
 * 센서 매핑:
 * - DI1, DI3: Lane 1 레이저 센서
 * - DI0, DI2: Lane 2 레이저 센서
 *
 * 신호등 매핑:
 * - DO0: Lane 1 초록 신호
 * - DO1: Lane 1 빨강 신호
 * - DO2: Lane 2 초록 신호
 * - DO3: Lane 2 빨강 신호
 *
 * 입출차 감지 로직:
 * - DI1 ON && DI3 OFF => Lane1 입차 (외부→내부)
 * - DI3 ON && DI1 OFF => Lane1 출차 (내부→외부)
 * - DI0 ON && DI2 OFF => Lane2 입차 (외부→내부)
 * - DI2 ON && DI0 OFF => Lane2 출차 (내부→외부)
 */

/**
 * @typedef {Object} LaneConfig
 * @property {number} sensor1_di - 센서 1 DI 채널 (0-3)
 * @property {number} sensor2_di - 센서 2 DI 채널 (0-3)
 * @property {number} green_do - 초록 신호등 DO 채널 (0-3)
 * @property {number} red_do - 빨강 신호등 DO 채널 (0-3)
 */

/**
 * @typedef {Object} HipassConfig
 * @property {LaneConfig} lane1 - Lane 1 설정
 * @property {LaneConfig} lane2 - Lane 2 설정
 * @property {boolean} invert_sensor_logic - 센서 로직 반전 여부
 */

/**
 * @typedef {Object} LaneState
 * @property {boolean} sensor1_prev - 이전 센서 1 상태
 * @property {boolean} sensor2_prev - 이전 센서 2 상태
 * @property {number} enter_count - 입차 횟수
 * @property {number} exit_count - 출차 횟수
 * @property {string|null} last_event - 마지막 이벤트
 * @property {string} current_state - 현재 상태
 */

// 전역 상태
/** @type {EventSource|null} */
let eventSource = null;

/** @type {number} */
let reconnectAttempts = 0;

const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAY = 2000;

// 하이패스 설정 (서버에서 로드)
/** @type {HipassConfig} */
let hipassConfig = {
    lane1: { sensor1_di: 1, sensor2_di: 3, green_do: 0, red_do: 1 },
    lane2: { sensor1_di: 0, sensor2_di: 2, green_do: 2, red_do: 3 },
    invert_sensor_logic: false
};

// Lane 상태 저장
/** @type {{lane1: LaneState, lane2: LaneState}} */
const laneState = {
    lane1: {
        sensor1_prev: false,
        sensor2_prev: false,
        enter_count: 0,
        exit_count: 0,
        last_event: null,
        current_state: '대기중'
    },
    lane2: {
        sensor1_prev: false,
        sensor2_prev: false,
        enter_count: 0,
        exit_count: 0,
        last_event: null,
        current_state: '대기중'
    }
};

// 이벤트 로그
/** @type {Array<Object>} */
const eventLog = [];

const MAX_EVENTS = 100;

/**
 * 초기화
 */
document.addEventListener('DOMContentLoaded', async function() {
    console.log('UWB 이륜차 하이패스 모니터링 시작');

    // 하이패스 설정 로드
    await loadHipassConfig();

    connectSSE();
});

/**
 * 하이패스 설정 로드
 *
 * @returns {Promise<void>}
 */
async function loadHipassConfig() {
    try {
        const response = await fetch('/api/hipass/config');

        if (response.ok) {
            const config = await response.json();

            // 설정 검증
            if (validateConfig(config)) {
                hipassConfig = config;
                console.log('✅ 하이패스 설정 로드 성공:', hipassConfig);
            } else {
                console.warn('⚠️ 설정 값이 유효하지 않습니다. 기본값을 사용합니다.');
                showNotification('warning', '설정 값이 유효하지 않아 기본값을 사용합니다.');
            }
        } else {
            const errorData = await response.json().catch(() => ({}));
            console.error('⚠️ 설정 로드 실패:', response.status, errorData);
            showNotification('warning', `설정 로드 실패 (${response.status}), 기본값 사용`);
        }
    } catch (error) {
        console.error('❌ 하이패스 설정 로드 오류:', error);
        showNotification('error', '설정 서버 연결 실패, 기본값 사용');
    }
}

/**
 * 설정 값 검증
 *
 * @param {Object} config - 하이패스 설정 객체
 * @returns {boolean} 유효성 여부
 */
function validateConfig(config) {
    if (!config || !config.lane1 || !config.lane2) {
        return false;
    }

    // DI/DO 채널 범위 검증 (0-3)
    const channels = [
        config.lane1.sensor1_di, config.lane1.sensor2_di,
        config.lane1.green_do, config.lane1.red_do,
        config.lane2.sensor1_di, config.lane2.sensor2_di,
        config.lane2.green_do, config.lane2.red_do
    ];

    return channels.every(ch => typeof ch === 'number' && ch >= 0 && ch <= 3);
}

/**
 * 사용자 알림 표시
 *
 * @param {string} type - 알림 타입 (success, warning, error)
 * @param {string} message - 알림 메시지
 */
function showNotification(type, message) {
    // 간단한 콘솔 알림 (필요시 UI 토스트로 확장 가능)
    const emoji = { success: '✅', warning: '⚠️', error: '❌' };
    console.log(`${emoji[type] || 'ℹ️'} ${message}`);

    // TODO: UI 토스트 알림 추가 (Bootstrap Toast 등)
}

/**
 * SSE 연결 시작
 *
 * EventSource를 생성하여 서버와 실시간 연결을 설정합니다.
 * 연결 실패 시 자동 재연결을 시도합니다 (최대 5회).
 *
 * @returns {void}
 */
function connectSSE() {
    if (eventSource) {
        eventSource.close();
    }

    console.log('SSE 연결 시도...');
    updateConnectionStatus('connecting');

    eventSource = new EventSource('/api/events');

    eventSource.onopen = function() {
        console.log('✅ SSE 연결 성공');
        reconnectAttempts = 0;
        updateConnectionStatus('connected');
    };

    eventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);

            if (data.type === 'initial') {
                console.log('📊 초기 상태 수신:', data);
                processInitialState(data.devices);
            } else if (data.type === 'update') {
                console.log('🔄 업데이트 수신:', data);
                processUpdate(data.devices);
            }
        } catch (error) {
            console.error('❌ 데이터 파싱 오류:', error);
        }
    };

    eventSource.onerror = function(error) {
        console.error('❌ SSE 오류:', error);
        eventSource.close();
        updateConnectionStatus('disconnected');

        if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
            reconnectAttempts++;
            console.log(`🔄 재연결 시도 ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS}...`);
            setTimeout(connectSSE, RECONNECT_DELAY * reconnectAttempts);
        } else {
            console.error('❌ 최대 재연결 시도 횟수 초과');
            addEventLog('시스템', '연결 실패', 'error', '서버 연결에 실패했습니다. 페이지를 새로고침하세요.');
        }
    };
}

/**
 * 연결 상태 UI 업데이트
 *
 * @param {string} status - 연결 상태 ('connected' | 'connecting' | 'disconnected')
 * @returns {void}
 */
function updateConnectionStatus(status) {
    const statusBadge = document.getElementById('connectionStatus');
    const statusText = document.getElementById('connectionText');
    const indicator = statusBadge.querySelector('.status-indicator');

    if (status === 'connected') {
        statusBadge.className = 'status-badge connected';
        indicator.className = 'status-indicator active';
        statusText.textContent = '연결됨';
    } else if (status === 'connecting') {
        statusBadge.className = 'status-badge';
        indicator.className = 'status-indicator';
        statusText.textContent = '연결 중...';
    } else {
        statusBadge.className = 'status-badge disconnected';
        indicator.className = 'status-indicator inactive';
        statusText.textContent = '연결 끊김';
    }
}

/**
 * 초기 상태 처리
 *
 * @param {Object} devices - 장비 상태 객체
 * @param {Object} devices.device1 - Device1 상태
 * @param {boolean[]} devices.device1.inputs - DI 상태 배열
 * @param {boolean[]} devices.device1.outputs - DO 상태 배열
 */
function processInitialState(devices) {
    if (!devices || !devices.device1) {
        console.warn('⚠️ device1 데이터 없음');
        return;
    }

    const device = devices.device1;

    // 센서 로직 반전 적용 (.env 설정 사용)
    const di0 = hipassConfig.invert_sensor_logic ? !device.inputs[0] : device.inputs[0];
    const di1 = hipassConfig.invert_sensor_logic ? !device.inputs[1] : device.inputs[1];
    const di2 = hipassConfig.invert_sensor_logic ? !device.inputs[2] : device.inputs[2];
    const di3 = hipassConfig.invert_sensor_logic ? !device.inputs[3] : device.inputs[3];

    // Lane 1 센서 상태 (DI1, DI3)
    updateSensorState('lane1', 'di1', device.inputs[1]);
    updateSensorState('lane1', 'di3', device.inputs[3]);

    // Lane 2 센서 상태 (DI0, DI2)
    updateSensorState('lane2', 'di0', device.inputs[0]);
    updateSensorState('lane2', 'di2', device.inputs[2]);

    // 신호등 상태 (DO0-DO3)
    updateTrafficLight('lane1', 'green', device.outputs[0]);
    updateTrafficLight('lane1', 'red', device.outputs[1]);
    updateTrafficLight('lane2', 'green', device.outputs[2]);
    updateTrafficLight('lane2', 'red', device.outputs[3]);

    // 이전 상태 저장 (반전 적용된 값)
    laneState.lane1.di1_prev = di1;
    laneState.lane1.di3_prev = di3;
    laneState.lane2.di0_prev = di0;
    laneState.lane2.di2_prev = di2;
}

/**
 * 업데이트 처리
 *
 * @param {Object} devices - 장비 상태 객체
 */
function processUpdate(devices) {
    if (!devices || !devices.device1) {
        return;
    }

    const device = devices.device1;
    const inputs = device.inputs;
    const outputs = device.outputs;

    // Lane 1 센서 상태 업데이트
    updateSensorState('lane1', 'di0', inputs[0]);
    updateSensorState('lane1', 'di1', inputs[1]);

    // Lane 2 센서 상태 업데이트
    updateSensorState('lane2', 'di2', inputs[2]);
    updateSensorState('lane2', 'di3', inputs[3]);

    // 신호등 상태 업데이트
    updateTrafficLight('lane1', 'green', outputs[0]);
    updateTrafficLight('lane1', 'red', outputs[1]);
    updateTrafficLight('lane2', 'green', outputs[2]);
    updateTrafficLight('lane2', 'red', outputs[3]);

    // === Lane 1 입출차 감지 로직 (DI1, DI3 사용) ===
    // 센서 로직 반전 적용 (.env 설정 사용)
    let di1 = hipassConfig.invert_sensor_logic ? !inputs[1] : inputs[1];
    let di3 = hipassConfig.invert_sensor_logic ? !inputs[3] : inputs[3];
    const di1_prev = laneState.lane1.di1_prev;
    const di3_prev = laneState.lane1.di3_prev;

    // DI1이 OFF→ON으로 변경되었고, 그 순간 DI3이 OFF면 => 입차
    if (!di1_prev && di1 && !di3) {
        detectVehicleEnter('lane1');
    }
    // DI3이 OFF→ON으로 변경되었고, 그 순간 DI1이 OFF면 => 출차
    else if (!di3_prev && di3 && !di1) {
        detectVehicleExit('lane1');
    }

    // === Lane 2 입출차 감지 로직 (DI0, DI2 사용) ===
    // 센서 로직 반전 적용 (.env 설정 사용)
    let di0 = hipassConfig.invert_sensor_logic ? !inputs[0] : inputs[0];
    let di2 = hipassConfig.invert_sensor_logic ? !inputs[2] : inputs[2];
    const di0_prev = laneState.lane2.di0_prev;
    const di2_prev = laneState.lane2.di2_prev;

    // DI0이 OFF→ON으로 변경되었고, 그 순간 DI2가 OFF면 => 입차
    if (!di0_prev && di0 && !di2) {
        detectVehicleEnter('lane2');
    }
    // DI2가 OFF→ON으로 변경되었고, 그 순간 DI0이 OFF면 => 출차
    else if (!di2_prev && di2 && !di0) {
        detectVehicleExit('lane2');
    }

    // 이전 상태 업데이트
    laneState.lane1.di1_prev = di1;
    laneState.lane1.di3_prev = di3;
    laneState.lane2.di0_prev = di0;
    laneState.lane2.di2_prev = di2;
}

/**
 * 센서 상태 업데이트
 *
 * 주의: CIE-H14A의 DI 입력은 센서 타입에 따라 반전될 수 있습니다
 * - Normal Open (NO): 차단 시 ON (true)
 * - Normal Close (NC): 차단 시 OFF (false)
 *
 * 현재 설정: .env 파일의 HIPASS_INVERT_SENSOR_LOGIC에서 설정
 *
 * @param {string} lane - Lane ID (lane1, lane2)
 * @param {string} sensor - 센서 ID (di0, di1, di2, di3)
 * @param {boolean} isActive - 센서 활성화 상태
 */
function updateSensorState(lane, sensor, isActive) {
    const sensorId = `${lane}_${sensor}`;
    const sensorElement = document.getElementById(sensorId);

    if (sensorElement) {
        // 센서 로직 반전 옵션 (.env에서 로드)
        const actualState = hipassConfig.invert_sensor_logic ? !isActive : isActive;

        if (actualState) {
            sensorElement.classList.add('active');
        } else {
            sensorElement.classList.remove('active');
        }
    }
}

/**
 * 신호등 상태 UI 업데이트
 *
 * @param {string} lane - Lane ID (lane1, lane2)
 * @param {string} color - 신호등 색상 ('green' | 'red')
 * @param {boolean} isOn - 점등 여부
 * @returns {void}
 */
function updateTrafficLight(lane, color, isOn) {
    const lightId = `${lane}_${color}`;
    const lightElement = document.getElementById(lightId);

    if (lightElement) {
        if (isOn) {
            lightElement.classList.add('on');
        } else {
            lightElement.classList.remove('on');
        }
    }
}

/**
 * 차량 입차 감지 및 처리
 *
 * 외부측 센서가 먼저 감지되면 입차로 판단합니다.
 * 입차 통계 갱신, UI 애니메이션, 이벤트 로그 기록을 수행합니다.
 *
 * @param {string} lane - Lane ID (lane1, lane2)
 * @returns {void}
 */
function detectVehicleEnter(lane) {
    console.log(`🚗 ${lane.toUpperCase()} 입차 감지!`);

    // 상태 업데이트
    laneState[lane].enter_count++;
    laneState[lane].current_state = '입차';
    laneState[lane].last_event = '입차';

    // UI 업데이트
    updateLaneStatus(lane, 'enter');
    animateVehicle(lane, 'enter');

    // 이벤트 로그 추가
    addEventLog(
        lane.toUpperCase(),
        '입차 감지',
        'enter',
        `차량이 ${lane === 'lane1' ? 'Lane 1' : 'Lane 2'}로 진입했습니다`
    );

    // 자동 신호등 제어 (옵션)
    // autoControlTrafficLight(lane, 'enter');
}

/**
 * 차량 출차 감지 및 처리
 *
 * 내부측 센서가 먼저 감지되면 출차로 판단합니다.
 * 출차 통계 갱신, UI 애니메이션, 이벤트 로그 기록을 수행합니다.
 *
 * @param {string} lane - Lane ID (lane1, lane2)
 * @returns {void}
 */
function detectVehicleExit(lane) {
    console.log(`🚗 ${lane.toUpperCase()} 출차 감지!`);

    // 상태 업데이트
    laneState[lane].exit_count++;
    laneState[lane].current_state = '출차';
    laneState[lane].last_event = '출차';

    // UI 업데이트
    updateLaneStatus(lane, 'exit');
    animateVehicle(lane, 'exit');

    // 이벤트 로그 추가
    addEventLog(
        lane.toUpperCase(),
        '출차 감지',
        'exit',
        `차량이 ${lane === 'lane1' ? 'Lane 1' : 'Lane 2'}에서 출차했습니다`
    );

    // 자동 신호등 제어 (옵션)
    // autoControlTrafficLight(lane, 'exit');
}

/**
 * Lane 상태 UI 업데이트
 *
 * 통계 정보 (입차/출차 횟수, 현재 상태)를 UI에 반영합니다.
 *
 * @param {string} lane - Lane ID (lane1, lane2)
 * @param {string} action - 동작 ('enter' | 'exit')
 * @returns {void}
 */
function updateLaneStatus(lane, action) {
    const laneNum = lane === 'lane1' ? '1' : '2';

    // 상태 배지 업데이트
    const statusBadge = document.getElementById(`${lane}Status`);
    const statusText = statusBadge.querySelector('span:last-child');

    if (action === 'enter') {
        statusBadge.className = 'status-badge';
        statusBadge.style.background = 'rgba(16, 185, 129, 0.2)';
        statusBadge.style.color = '#10b981';
        statusBadge.style.border = '2px solid #10b981';
        statusText.textContent = '입차 중';
    } else {
        statusBadge.className = 'status-badge';
        statusBadge.style.background = 'rgba(249, 115, 22, 0.2)';
        statusBadge.style.color = '#f97316';
        statusBadge.style.border = '2px solid #f97316';
        statusText.textContent = '출차 중';
    }

    // 2초 후 대기 상태로 복귀
    setTimeout(() => {
        statusBadge.className = 'status-badge';
        statusBadge.style.background = '';
        statusBadge.style.color = '';
        statusBadge.style.border = '';
        statusText.textContent = '대기';
        laneState[lane].current_state = '대기중';
    }, 2000);

    // 통계 업데이트
    document.getElementById(`${lane}_current_state`).textContent = laneState[lane].current_state;
    document.getElementById(`${lane}_enter_count`).textContent = laneState[lane].enter_count;
    document.getElementById(`${lane}_exit_count`).textContent = laneState[lane].exit_count;
    document.getElementById(`${lane}_last_event`).textContent = laneState[lane].last_event;
}

/**
 * 차량 이동 애니메이션 재생
 *
 * CSS 클래스를 추가/제거하여 차량과 화살표 애니메이션을 재생합니다.
 *
 * @param {string} lane - Lane ID (lane1, lane2)
 * @param {string} action - 동작 ('enter' | 'exit')
 * @returns {void}
 */
function animateVehicle(lane, action) {
    const vehicle = document.getElementById(`${lane}_vehicle`);
    const arrowEnter = document.getElementById(`${lane}_arrow_enter`);
    const arrowExit = document.getElementById(`${lane}_arrow_exit`);

    // 기존 애니메이션 제거
    vehicle.classList.remove('entering', 'exiting');
    arrowEnter.classList.remove('entering');
    arrowExit.classList.remove('exiting');

    // 새 애니메이션 시작
    setTimeout(() => {
        if (action === 'enter') {
            vehicle.classList.add('entering');
            arrowEnter.classList.add('entering');
        } else {
            vehicle.classList.add('exiting');
            arrowExit.classList.add('exiting');
        }

        // 애니메이션 완료 후 제거
        setTimeout(() => {
            vehicle.classList.remove('entering', 'exiting');
            arrowEnter.classList.remove('entering');
            arrowExit.classList.remove('exiting');
        }, 2000);
    }, 50);
}

/**
 * 이벤트 로그 추가
 *
 * 입출차 이벤트를 로그 배열에 추가하고 UI를 갱신합니다.
 * 최대 100개까지 저장하며 초과 시 오래된 로그를 제거합니다.
 *
 * @param {string} lane - Lane 이름 (예: 'LANE1', 'LANE2')
 * @param {string} title - 이벤트 제목
 * @param {string} type - 이벤트 타입 ('enter' | 'exit' | 'error')
 * @param {string} description - 이벤트 설명
 * @returns {void}
 */
function addEventLog(lane, title, type, description) {
    const timestamp = new Date();
    const event = {
        lane,
        title,
        type,
        description,
        timestamp: timestamp.toLocaleString('ko-KR')
    };

    // 로그 추가 (최대 100개)
    eventLog.unshift(event);
    if (eventLog.length > MAX_EVENTS) {
        eventLog.pop();
    }

    // UI 업데이트
    renderEventLog();
}

/**
 * 이벤트 로그 UI 렌더링
 *
 * eventLog 배열의 내용을 HTML로 변환하여 화면에 표시합니다.
 *
 * @returns {void}
 */
function renderEventLog() {
    const eventList = document.getElementById('eventList');

    if (eventLog.length === 0) {
        eventList.innerHTML = `
            <div style="text-align: center; color: var(--text-secondary); padding: 2rem;">
                이벤트가 없습니다
            </div>
        `;
        return;
    }

    eventList.innerHTML = eventLog.map(event => {
        let icon = '🚗';
        if (event.type === 'enter') icon = '🚗➡️';
        else if (event.type === 'exit') icon = '⬅️🚗';
        else if (event.type === 'error') icon = '⚠️';

        return `
            <div class="event-item ${event.type}">
                <div class="event-content">
                    <div class="event-icon">${icon}</div>
                    <div class="event-details">
                        <div class="event-title">${event.lane} - ${event.title}</div>
                        <div class="event-time">${event.timestamp}</div>
                    </div>
                </div>
                <div style="color: var(--text-secondary); font-size: 0.9rem;">
                    ${event.description}
                </div>
            </div>
        `;
    }).join('');
}

/**
 * 신호등 수동 제어
 */
async function toggleOutput(deviceId, channel) {
    try {
        const response = await fetch(`/api/devices/${deviceId}/output/${channel}/toggle`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error('신호등 제어 실패');
        }

        const result = await response.json();
        console.log(`✅ 신호등 제어 성공:`, result);

        const laneNum = channel < 2 ? 1 : 2;
        const lightType = channel % 2 === 0 ? '초록' : '빨강';

        addEventLog(
            `Lane ${laneNum}`,
            '신호등 제어',
            'control',
            `${lightType} 신호등을 ${result.state ? 'ON' : 'OFF'}했습니다`
        );
    } catch (error) {
        console.error('❌ 신호등 제어 오류:', error);
        addEventLog(
            '시스템',
            '제어 오류',
            'error',
            '신호등 제어에 실패했습니다'
        );
    }
}

/**
 * 자동 신호등 제어 (선택 사항)
 */
function autoControlTrafficLight(lane, action) {
    const laneNum = lane === 'lane1' ? 1 : 2;
    const baseChannel = (laneNum - 1) * 2;

    if (action === 'enter') {
        // 입차 시: 빨강 신호 ON
        controlOutput('device1', baseChannel + 1, true);
    } else {
        // 출차 시: 초록 신호 ON (선택 사항)
        // controlOutput('device1', baseChannel, true);
    }
}

/**
 * 신호등 제어 API 호출
 */
async function controlOutput(deviceId, channel, state) {
    try {
        const response = await fetch(`/api/devices/${deviceId}/output/${channel}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ state })
        });

        if (!response.ok) {
            throw new Error('신호등 제어 실패');
        }

        console.log(`✅ 자동 신호등 제어: DO${channel} = ${state}`);
    } catch (error) {
        console.error('❌ 자동 신호등 제어 오류:', error);
    }
}

// 페이지 언로드 시 SSE 연결 종료
window.addEventListener('beforeunload', function() {
    if (eventSource) {
        eventSource.close();
    }
});

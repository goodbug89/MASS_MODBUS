"""
Flask API 라우트 (멀티 디바이스 지원)

OWASP Secure Coding Practices를 적용한 REST API 및 SSE 엔드포인트
4대의 CIE-H14A 장비를 동시에 제어합니다.
"""

import json
import time
import threading
from functools import wraps
from flask import Blueprint, jsonify, request, Response, current_app
from app import modbus_clients, api_monitor_data
from app.validators import (
    ValidationError, validate_channel, validate_boolean,
    validate_json_payload, validate_device_id
)

# 자동 꺼짐 타이머 관리 (device_id_channel: Timer)
_auto_off_timers = {}
_timer_lock = threading.Lock()

# Blueprint 생성
bp = Blueprint('api', __name__)

# Rate limiting (간단한 구현 - 전체 시스템 합산)
_system_request_counts = []  # 전체 시스템의 요청 타임스탬프 리스트
_RATE_LIMIT_WINDOW = 60  # 초
_RATE_LIMIT_MAX_REQUESTS = 500  # 분당 최대 요청 수 (전체 시스템 합산)


def rate_limit(max_requests=500, window=60):
    """
    Rate limiting 데코레이터 (전체 시스템 합산)

    모든 클라이언트의 요청을 합산하여 제한합니다.

    Args:
        max_requests: 시간 창 내 최대 요청 수 (전체 시스템)
        window: 시간 창 크기 (초)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            global _system_request_counts

            current_time = time.time()

            # Rate limit 데이터 정리 (오래된 항목 제거)
            _system_request_counts = [
                timestamp for timestamp in _system_request_counts
                if current_time - timestamp < window
            ]

            # Rate limit 확인 (전체 시스템)
            if len(_system_request_counts) >= max_requests:
                current_app.logger.warning(
                    f"Rate limit exceeded: System total "
                    f"({len(_system_request_counts)} requests in {window}s), "
                    f"Client: {request.remote_addr}"
                )
                return jsonify({
                    'error': '시스템 요청 한도를 초과했습니다',
                    'message': f'전체 시스템 요청이 {max_requests}회/분을 초과했습니다',
                    'retry_after': window,
                    'current_requests': len(_system_request_counts)
                }), 429

            # 요청 기록 (전체 시스템)
            _system_request_counts.append(current_time)

            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_api_key(func):
    """
    API 키 인증 데코레이터

    환경 변수 SIMULATOR_API_KEY가 설정된 경우, 요청 헤더의 X-API-Key와 비교하여 인증합니다.
    설정되지 않은 경우 인증을 건너뜁니다 (개발 환경용).

    사용법:
        @bp.route('/api/protected')
        @require_api_key
        def protected_endpoint():
            return jsonify({'message': 'authorized'})

    클라이언트 요청:
        curl -H "X-API-Key: your-secret-key" http://localhost:5000/api/protected
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        import os

        # 환경 변수에서 API 키 로드
        expected_api_key = os.getenv('SIMULATOR_API_KEY')

        # API 키가 설정되지 않은 경우 인증 건너뛰기 (개발 환경)
        if not expected_api_key:
            current_app.logger.warning(
                "SIMULATOR_API_KEY not set - API authentication disabled. "
                "Set SIMULATOR_API_KEY in .env for production."
            )
            return func(*args, **kwargs)

        # 요청 헤더에서 API 키 확인
        provided_api_key = request.headers.get('X-API-Key')

        if not provided_api_key:
            current_app.logger.warning(
                f"API key missing from {request.remote_addr} for {request.path}"
            )
            return jsonify({
                'error': 'Unauthorized',
                'message': 'API key required. Provide X-API-Key header.'
            }), 401

        if provided_api_key != expected_api_key:
            current_app.logger.warning(
                f"Invalid API key from {request.remote_addr} for {request.path}"
            )
            return jsonify({
                'error': 'Forbidden',
                'message': 'Invalid API key'
            }), 403

        # 인증 성공
        return func(*args, **kwargs)

    return wrapper


def handle_errors(func):
    """
    에러 처리 데코레이터

    예외를 포착하고 안전한 에러 메시지를 반환합니다.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            # 입력 검증 실패
            current_app.logger.warning(f"Validation error: {e}")
            return jsonify({
                'error': 'Invalid input',
                'message': str(e)
            }), 400
        except Exception as e:
            # 예상치 못한 에러
            current_app.logger.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
            # 상세한 에러 정보는 로그에만 기록, 클라이언트에는 일반적인 메시지만 전달
            return jsonify({
                'error': 'Internal server error',
                'message': 'An unexpected error occurred'
            }), 500
    return wrapper


def _schedule_auto_off(device_id: str, channel: int, duration_ms: int, app) -> None:
    """
    자동 꺼짐 타이머 설정

    지정된 시간(밀리초) 후에 출력을 자동으로 끕니다.
    동일한 device_id/channel에 기존 타이머가 있으면 취소 후 새로 설정합니다.

    Args:
        device_id: 장비 ID
        channel: 출력 채널 번호 (0-3)
        duration_ms: 자동 꺼짐까지의 시간 (밀리초)
        app: Flask 애플리케이션 컨텍스트
    """
    global _auto_off_timers

    timer_key = f"{device_id}_{channel}"
    duration_sec = duration_ms / 1000.0

    def auto_off_callback():
        """타이머 콜백: 출력 끄기"""
        with app.app_context():
            try:
                if device_id in modbus_clients:
                    client = modbus_clients[device_id]
                    success = client.write_output(channel, False)
                    if success:
                        app.logger.info(
                            f"[{device_id}] Auto-off triggered: channel={channel}, "
                            f"duration={duration_ms}ms"
                        )
                    else:
                        app.logger.error(
                            f"[{device_id}] Auto-off failed: channel={channel}"
                        )
            except Exception as e:
                app.logger.error(f"[{device_id}] Auto-off error: {e}")
            finally:
                # 타이머 정리
                with _timer_lock:
                    if timer_key in _auto_off_timers:
                        del _auto_off_timers[timer_key]

    with _timer_lock:
        # 기존 타이머 취소
        if timer_key in _auto_off_timers:
            old_timer = _auto_off_timers[timer_key]
            old_timer.cancel()
            app.logger.debug(f"[{device_id}] Cancelled existing auto-off timer for channel {channel}")

        # 새 타이머 설정
        timer = threading.Timer(duration_sec, auto_off_callback)
        timer.daemon = True
        timer.start()
        _auto_off_timers[timer_key] = timer

        app.logger.info(
            f"[{device_id}] Auto-off scheduled: channel={channel}, duration={duration_ms}ms"
        )


@bp.route('/')
def index():
    """
    메인 페이지

    Returns:
        HTML: 정적 index.html 파일
    """
    return current_app.send_static_file('index.html')


@bp.route('/docs')
def api_docs():
    """
    API 문서 페이지

    Returns:
        HTML: API 문서 페이지
    """
    return current_app.send_static_file('docs.html')


@bp.route('/health')
@handle_errors
def health_check():
    """
    헬스 체크 엔드포인트 (멀티 디바이스)

    Returns:
        JSON: 서버 및 Modbus 연결 상태
    """
    if not modbus_clients:
        return jsonify({
            'status': 'healthy',
            'modbus_connected': False,
            'total_devices': 0,
            'connected_devices': 0
        })

    connected_count = sum(1 for client in modbus_clients.values() if client.is_connected())

    return jsonify({
        'status': 'healthy',
        'modbus_connected': connected_count > 0,
        'total_devices': len(modbus_clients),
        'connected_devices': connected_count
    })


@bp.route('/api/status')
@handle_errors
@rate_limit(max_requests=60, window=60)
def get_status():
    """
    전체 장비 상태 조회 (멀티 디바이스)

    Returns:
        JSON: 전체 장비의 연결 상태 및 입출력 상태
        {
            "devices": {
                "device1": {...},
                "device2": {...},
                ...
            },
            "summary": {
                "total_devices": 4,
                "connected_devices": 3,
                "disconnected_devices": 1
            }
        }
    """
    if not modbus_clients:
        return jsonify({
            'error': 'No devices configured'
        }), 500

    all_status = {}
    connected_count = 0

    for device_id, client in modbus_clients.items():
        status = client.get_status()

        # 장비 이름 추가
        device_config = current_app.config['DEVICES'].get(device_id, {})
        status['name'] = device_config.get('name', device_id)

        all_status[device_id] = status

        if status['connected']:
            connected_count += 1

    return jsonify({
        'devices': all_status,
        'summary': {
            'total_devices': len(modbus_clients),
            'connected_devices': connected_count,
            'disconnected_devices': len(modbus_clients) - connected_count
        }
    })


# ============================================================================
# 레거시 API (하위 호환성 - 첫 번째 장비를 기본값으로 사용)
# ============================================================================

@bp.route('/api/output/<int:channel>', methods=['POST'])
@handle_errors
@rate_limit(max_requests=120, window=60)
def control_output(channel):
    """
    [DEPRECATED] 특정 출력 채널 제어 (첫 번째 장비 사용)

    대신 /api/devices/<device_id>/output/<channel>를 사용하세요.
    """
    if not modbus_clients:
        return jsonify({'error': 'No devices configured'}), 500

    # 첫 번째 장비 사용
    first_device_id = list(modbus_clients.keys())[0]
    return control_device_output(first_device_id, channel)


@bp.route('/api/output/<int:channel>/toggle', methods=['POST'])
@handle_errors
@rate_limit(max_requests=120, window=60)
def toggle_output(channel):
    """
    [DEPRECATED] 출력 채널 토글 (첫 번째 장비 사용)

    대신 /api/devices/<device_id>/output/<channel>/toggle을 사용하세요.
    """
    if not modbus_clients:
        return jsonify({'error': 'No devices configured'}), 500

    # 첫 번째 장비 사용
    first_device_id = list(modbus_clients.keys())[0]
    return toggle_device_output(first_device_id, channel)


@bp.route('/api/config')
@handle_errors
@rate_limit(max_requests=10, window=60)
def get_config():
    """
    [DEPRECATED] 현재 Modbus 설정 조회 (모든 장비 설정)

    대신 /api/devices를 사용하세요.
    """
    return get_devices_list()


@bp.route('/api/monitor')
@handle_errors
@rate_limit(max_requests=20, window=60)
def get_monitor():
    """
    API 모니터링 정보 조회

    Returns:
        JSON: API 요청 통계 및 최근 이력
    """
    uptime = time.time() - api_monitor_data['start_time']

    # 최근 10개 요청만 반환
    recent_history = list(api_monitor_data['history'])[-10:]

    # 최근 1분간 통계
    one_minute_ago = time.time() - 60
    recent_requests = [h for h in api_monitor_data['history'] if h['timestamp'] > one_minute_ago]
    recent_failed = sum(1 for h in recent_requests if not h['success'])

    # 평균 응답 시간
    avg_duration = sum(h['duration'] for h in recent_requests) / len(recent_requests) if recent_requests else 0

    return jsonify({
        'uptime': round(uptime, 2),
        'total_requests': api_monitor_data['total_requests'],
        'failed_requests': api_monitor_data['failed_requests'],
        'success_rate': round((api_monitor_data['total_requests'] - api_monitor_data['failed_requests']) / max(api_monitor_data['total_requests'], 1) * 100, 2),
        'recent_1min': {
            'requests': len(recent_requests),
            'failed': recent_failed,
            'avg_duration_ms': round(avg_duration, 2)
        },
        'recent_history': recent_history,
        'last_check': time.time()
    })


@bp.route('/api/get_sensor')
@handle_errors
@rate_limit(max_requests=60, window=60)
def get_sensor():
    """
    센서 엔드포인트 (DI 감지 시 호출됨)

    Query Parameters:
        id: 장비 ID
        di_states: DI 상태 (예: "1,0,0,0")

    Returns:
        JSON: 센서 수신 결과
    """
    # 장비 ID 검증
    try:
        device_id = request.args.get('id', 'unknown')
        if device_id != 'unknown':
            device_id = validate_device_id(device_id)
    except ValidationError as e:
        return jsonify({
            'error': 'Invalid device ID',
            'message': str(e)
        }), 400

    # DI 상태 검증
    di_states = request.args.get('di_states', '')
    if di_states:
        # CSV 형식 검증 (0 또는 1만 허용)
        if not all(c in '0,1' for c in di_states):
            return jsonify({
                'error': 'Invalid DI states format'
            }), 400

    # 밀리초 단위 타임스탬프
    timestamp_ms = int(time.time() * 1000)

    current_app.logger.info(
        f"[Sensor Endpoint] DI detection received - "
        f"Device ID: {device_id}, DI States: [{di_states}], "
        f"Time: {timestamp_ms}ms, Client: {request.remote_addr}"
    )

    return jsonify({
        'status': 'ok',
        'id': device_id,
        'di': di_states,
        'time': timestamp_ms
    })


@bp.route('/api/events')
@handle_errors
def sse_stream():
    """
    Server-Sent Events 스트림 (멀티 디바이스)

    모든 장비의 실시간 입출력 상태를 클라이언트에게 전송합니다.

    Returns:
        Response: SSE 스트림
    """
    def generate():
        """SSE 이벤트 생성기 (멀티 디바이스)"""
        if not modbus_clients:
            yield f"data: {json.dumps({'error': 'No devices configured'})}\n\n"
            return

        # 초기 상태 전송 (모든 장비)
        try:
            all_status = {}
            for device_id, client in modbus_clients.items():
                all_status[device_id] = client.get_status()

            yield f"data: {json.dumps({'type': 'initial', 'devices': all_status})}\n\n"
        except Exception as e:
            current_app.logger.error(f"SSE initial state error: {e}")
            yield f"data: {json.dumps({'error': 'Failed to get initial state'})}\n\n"
            return

        # 이전 상태 저장
        prev_all_status = {k: v.copy() for k, v in all_status.items()}

        # 주기적으로 상태 확인 및 전송
        while True:
            try:
                time.sleep(0.2)  # 200ms 간격

                # 모든 장비 상태 조회
                all_status = {}
                for device_id, client in modbus_clients.items():
                    all_status[device_id] = client.get_status()

                # 변화가 있는 장비만 전송 (효율성)
                changed_devices = {}
                for device_id, status in all_status.items():
                    prev_status = prev_all_status.get(device_id, {})

                    if (status.get('inputs') != prev_status.get('inputs') or
                        status.get('outputs') != prev_status.get('outputs') or
                        status.get('connected') != prev_status.get('connected') or
                        status.get('di_detection', {}) != prev_status.get('di_detection', {})):

                        changed_devices[device_id] = status

                # 변화가 있으면 전송
                if changed_devices:
                    yield f"data: {json.dumps({'type': 'update', 'devices': changed_devices})}\n\n"

                    # 이전 상태 업데이트
                    for device_id, status in changed_devices.items():
                        prev_all_status[device_id] = status.copy()

            except GeneratorExit:
                # 클라이언트 연결 끊김 (정상 동작)
                break
            except Exception as e:
                # 에러 발생 시 로깅하고 종료
                current_app.logger.error(f"SSE stream error: {e}")
                try:
                    yield f"data: {json.dumps({'error': 'Stream error occurred'})}\n\n"
                except:
                    pass
                break

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
            'X-Accel-Buffering': 'no',
            'X-Content-Type-Options': 'nosniff',
            'Connection': 'keep-alive'
        }
    )


@bp.errorhandler(404)
def not_found(error):
    """404 오류 핸들러"""
    current_app.logger.warning(f"404 Not Found: {request.path} from {request.remote_addr}")
    return jsonify({
        'error': 'Not found',
        'message': 'The requested resource was not found'
    }), 404


@bp.errorhandler(405)
def method_not_allowed(error):
    """405 오류 핸들러"""
    current_app.logger.warning(
        f"405 Method Not Allowed: {request.method} {request.path} from {request.remote_addr}"
    )
    return jsonify({
        'error': 'Method not allowed',
        'message': f'The {request.method} method is not allowed for this endpoint'
    }), 405


@bp.errorhandler(429)
def rate_limit_exceeded(error):
    """429 오류 핸들러"""
    return jsonify({
        'error': 'Rate limit exceeded',
        'message': 'Too many requests. Please try again later.'
    }), 429


@bp.errorhandler(500)
def internal_error(error):
    """500 오류 핸들러"""
    current_app.logger.error(f"Internal server error: {error}", exc_info=True)
    return jsonify({
        'error': 'Internal server error',
        'message': 'An unexpected error occurred'
    }), 500


# ============================================================================
# 멀티 디바이스 API (새로운 엔드포인트)
# ============================================================================

@bp.route('/api/devices')
@handle_errors
@rate_limit(max_requests=30, window=60)
def get_devices_list():
    """
    활성화된 장비 목록 조회

    Returns:
        JSON: 장비 목록
        {
            "devices": [
                {
                    "id": "device1",
                    "name": "Lane1",
                    "host": "192.168.10.***",
                    "connected": true
                },
                ...
            ]
        }
    """
    if not modbus_clients:
        return jsonify({
            'error': 'No devices configured'
        }), 500

    devices_list = []

    for device_id, client in modbus_clients.items():
        device_config = current_app.config['DEVICES'][device_id]

        devices_list.append({
            'id': device_id,
            'name': device_config['name'],
            'host': device_config['host'],
            'connected': client.is_connected()
        })

    return jsonify({'devices': devices_list})


@bp.route('/api/devices/<device_id>/status')
@handle_errors
@rate_limit(max_requests=60, window=60)
def get_device_status(device_id):
    """
    특정 장비 상태 조회

    Args:
        device_id: 장비 ID (예: device1, device2, ...)

    Returns:
        JSON: 장비 상태
    """
    # 장비 ID 검증
    device_id = validate_device_id(device_id, list(modbus_clients.keys()))

    if device_id not in modbus_clients:
        return jsonify({'error': 'Device not found'}), 404

    client = modbus_clients[device_id]
    status = client.get_status()

    # 장비 이름 추가
    device_config = current_app.config['DEVICES'][device_id]
    status['name'] = device_config['name']

    return jsonify(status)


@bp.route('/api/devices/<device_id>/output/<int:channel>', methods=['POST'])
@handle_errors
@rate_limit(max_requests=120, window=60)
def control_device_output(device_id, channel):
    """
    특정 장비의 출력 채널 제어

    Args:
        device_id: 장비 ID
        channel: 출력 채널 번호 (0-3)

    Body:
        {
            "state": true/false,
            "duration_ms": 1000  (선택, 밀리초 단위 자동 꺼짐 시간)
        }

    Returns:
        JSON: 제어 결과
    """
    # 장비 ID 검증
    device_id = validate_device_id(device_id, list(modbus_clients.keys()))

    if device_id not in modbus_clients:
        return jsonify({'error': 'Device not found'}), 404

    # 채널 번호 검증
    channel = validate_channel(channel)

    # Content-Type 검증
    if not request.is_json:
        return jsonify({'error': 'Content-Type must be application/json'}), 415

    # 요청 본문 파싱 및 검증
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Request body is empty'}), 400

    validate_json_payload(data, required_fields=['state'], optional_fields=['duration_ms'])
    state = validate_boolean(data['state'])

    # duration_ms 파라미터 확인 (선택적)
    duration_ms = data.get('duration_ms')
    if duration_ms is not None:
        try:
            duration_ms = int(duration_ms)
            if duration_ms < 10:
                return jsonify({
                    'error': 'Invalid duration_ms',
                    'message': 'duration_ms must be at least 10ms'
                }), 400
            if duration_ms > 3600000:  # 최대 1시간
                return jsonify({
                    'error': 'Invalid duration_ms',
                    'message': 'duration_ms must not exceed 3600000ms (1 hour)'
                }), 400
        except (TypeError, ValueError):
            return jsonify({
                'error': 'Invalid duration_ms',
                'message': 'duration_ms must be a positive integer (milliseconds)'
            }), 400

    # 출력 제어
    client = modbus_clients[device_id]
    success = client.write_output(channel, state)

    if success:
        # 자동 꺼짐 타이머 설정 (state=True이고 duration_ms가 지정된 경우)
        if state and duration_ms is not None:
            _schedule_auto_off(device_id, channel, duration_ms, current_app._get_current_object())

        current_app.logger.info(
            f"[{device_id}] Output control: channel={channel}, state={state}, "
            f"duration_ms={duration_ms}, client={request.remote_addr}"
        )

        response_data = {
            'success': True,
            'device_id': device_id,
            'channel': channel,
            'state': state
        }
        if duration_ms is not None:
            response_data['duration_ms'] = duration_ms
            response_data['auto_off'] = state  # state가 True일 때만 자동 꺼짐 활성화

        return jsonify(response_data)
    else:
        return jsonify({
            'error': 'Output control failed',
            'device_id': device_id,
            'channel': channel
        }), 500


@bp.route('/api/devices/<device_id>/output/<int:channel>/toggle', methods=['POST'])
@handle_errors
@rate_limit(max_requests=120, window=60)
def toggle_device_output(device_id, channel):
    """
    특정 장비의 출력 채널 토글

    Args:
        device_id: 장비 ID
        channel: 출력 채널 번호 (0-3)

    Returns:
        JSON: 토글 결과 및 새로운 상태
    """
    # 장비 ID 검증
    device_id = validate_device_id(device_id, list(modbus_clients.keys()))

    if device_id not in modbus_clients:
        return jsonify({'error': 'Device not found'}), 404

    # 채널 번호 검증
    channel = validate_channel(channel)

    # 출력 토글
    client = modbus_clients[device_id]
    success, new_state = client.toggle_output(channel)

    if success:
        current_app.logger.info(
            f"[{device_id}] Output toggle: channel={channel}, new_state={new_state}, "
            f"client={request.remote_addr}"
        )
        return jsonify({
            'success': True,
            'device_id': device_id,
            'channel': channel,
            'state': new_state
        })
    else:
        return jsonify({
            'error': 'Output toggle failed',
            'device_id': device_id,
            'channel': channel
        }), 500


# ============================================================================
# GET 방식 제어 API (간단한 테스트용)
# ============================================================================

@bp.route('/api/devices/<device_id>/output/<int:channel>/set', methods=['GET'])
@handle_errors
@rate_limit(max_requests=120, window=60)
def set_device_output_get(device_id, channel):
    """
    GET 방식으로 특정 장비의 출력 채널 제어 (테스트/간편 제어용)

    웹 브라우저에서 직접 URL로 접근하여 제어할 수 있습니다.

    Args:
        device_id: 장비 ID
        channel: 출력 채널 번호 (0-3)

    Query Parameters:
        state: on/off 또는 1/0 또는 true/false

    Examples:
        http://localhost:5000/api/devices/device2/output/1/set?state=on
        http://localhost:5000/api/devices/device2/output/1/set?state=off
        http://localhost:5000/api/devices/device2/output/1/set?state=1
        http://localhost:5000/api/devices/device2/output/1/set?state=0

    Returns:
        JSON: 제어 결과
    """
    # 장비 ID 검증
    device_id = validate_device_id(device_id, list(modbus_clients.keys()))

    if device_id not in modbus_clients:
        return jsonify({'error': 'Device not found'}), 404

    # 채널 번호 검증
    channel = validate_channel(channel)

    # state 파라미터 읽기
    state_param = request.args.get('state', '').lower()

    if not state_param:
        return jsonify({
            'error': 'Missing state parameter',
            'message': 'Please provide state parameter (on/off, 1/0, true/false)',
            'examples': [
                f'/api/devices/{device_id}/output/{channel}/set?state=on',
                f'/api/devices/{device_id}/output/{channel}/set?state=off'
            ]
        }), 400

    # state 값 파싱 (on/off, 1/0, true/false 모두 지원)
    if state_param in ['on', '1', 'true']:
        state = True
    elif state_param in ['off', '0', 'false']:
        state = False
    else:
        return jsonify({
            'error': 'Invalid state value',
            'message': f'State must be one of: on/off, 1/0, true/false (got: {state_param})'
        }), 400

    # 출력 제어
    client = modbus_clients[device_id]
    success = client.write_output(channel, state)

    if success:
        current_app.logger.info(
            f"[{device_id}] Output control (GET): channel={channel}, state={state}, "
            f"client={request.remote_addr}"
        )
        return jsonify({
            'success': True,
            'device_id': device_id,
            'channel': channel,
            'state': state,
            'message': f'DO{channel} turned {"ON" if state else "OFF"}'
        })
    else:
        return jsonify({
            'error': 'Output control failed',
            'device_id': device_id,
            'channel': channel
        }), 500


@bp.route('/api/devices/<device_id>/output/<int:channel>/on', methods=['GET'])
@handle_errors
@rate_limit(max_requests=120, window=60)
def turn_on_device_output(device_id, channel):
    """
    GET 방식으로 특정 장비의 출력 켜기 (간편 제어용)

    Args:
        device_id: 장비 ID
        channel: 출력 채널 번호 (0-3)

    Query Parameters:
        duration: 자동 꺼짐 시간 (밀리초, 선택적)

    Examples:
        http://localhost:5000/api/devices/device2/output/1/on
        http://localhost:5000/api/devices/device2/output/1/on?duration=500
        http://localhost:5000/api/devices/device2/output/1/on?duration=1000

    Returns:
        JSON: 제어 결과
    """
    # 장비 ID 검증
    device_id = validate_device_id(device_id, list(modbus_clients.keys()))

    if device_id not in modbus_clients:
        return jsonify({'error': 'Device not found'}), 404

    # 채널 번호 검증
    channel = validate_channel(channel)

    # duration 쿼리 파라미터 확인 (선택적)
    duration_ms = request.args.get('duration')
    if duration_ms is not None:
        try:
            duration_ms = int(duration_ms)
            if duration_ms < 10:
                return jsonify({
                    'error': 'Invalid duration',
                    'message': 'duration must be at least 10ms'
                }), 400
            if duration_ms > 3600000:  # 최대 1시간
                return jsonify({
                    'error': 'Invalid duration',
                    'message': 'duration must not exceed 3600000ms (1 hour)'
                }), 400
        except (TypeError, ValueError):
            return jsonify({
                'error': 'Invalid duration',
                'message': 'duration must be a positive integer (milliseconds)'
            }), 400

    # 출력 켜기
    client = modbus_clients[device_id]
    success = client.write_output(channel, True)

    if success:
        # 자동 꺼짐 타이머 설정 (duration이 지정된 경우)
        if duration_ms is not None:
            _schedule_auto_off(device_id, channel, duration_ms, current_app._get_current_object())

        current_app.logger.info(
            f"[{device_id}] Output ON (GET): channel={channel}, "
            f"duration={duration_ms}ms, client={request.remote_addr}"
        )

        response_data = {
            'success': True,
            'device_id': device_id,
            'channel': channel,
            'state': True,
            'message': f'DO{channel} turned ON'
        }
        if duration_ms is not None:
            response_data['duration_ms'] = duration_ms
            response_data['auto_off'] = True

        return jsonify(response_data)
    else:
        return jsonify({
            'error': 'Output control failed',
            'device_id': device_id,
            'channel': channel
        }), 500


@bp.route('/api/devices/<device_id>/output/<int:channel>/off', methods=['GET'])
@handle_errors
@rate_limit(max_requests=120, window=60)
def turn_off_device_output(device_id, channel):
    """
    GET 방식으로 특정 장비의 출력 끄기 (간편 제어용)

    Args:
        device_id: 장비 ID
        channel: 출력 채널 번호 (0-3)

    Example:
        http://localhost:5000/api/devices/device2/output/1/off

    Returns:
        JSON: 제어 결과
    """
    # 장비 ID 검증
    device_id = validate_device_id(device_id, list(modbus_clients.keys()))

    if device_id not in modbus_clients:
        return jsonify({'error': 'Device not found'}), 404

    # 채널 번호 검증
    channel = validate_channel(channel)

    # 출력 끄기
    client = modbus_clients[device_id]
    success = client.write_output(channel, False)

    if success:
        current_app.logger.info(
            f"[{device_id}] Output OFF (GET): channel={channel}, "
            f"client={request.remote_addr}"
        )
        return jsonify({
            'success': True,
            'device_id': device_id,
            'channel': channel,
            'state': False,
            'message': f'DO{channel} turned OFF'
        })
    else:
        return jsonify({
            'error': 'Output control failed',
            'device_id': device_id,
            'channel': channel
        }), 500


# ==============================================================================
# 시뮬레이터 제어 API
# ==============================================================================
#
# ⚠️ 보안 경고 ⚠️
#
# 이 엔드포인트들은 Docker 컨테이너를 제어하기 위해 subprocess를 사용합니다.
#
# 중요 보안 고려사항:
# 1. Docker 소켓 마운팅 (/var/run/docker.sock)은 호스트 시스템에 대한 루트 권한을 제공합니다.
# 2. 프로덕션 환경에서는 반드시 SIMULATOR_API_KEY를 설정하여 인증을 활성화하세요.
# 3. 이 코드는 하드코딩된 명령어만 사용합니다 - 사용자 입력을 subprocess에 전달하지 마세요!
# 4. 명령어 인젝션 방지를 위해 절대 사용자 입력을 명령어 파라미터로 사용하지 마세요.
#
# 안전한 예시:
#   subprocess.run(['docker', 'start', 'modbus-simulator'])  ✅ 안전
#
# 위험한 예시 (절대 사용 금지):
#   container_name = request.args.get('container')  # 사용자 입력
#   subprocess.run(['docker', 'start', container_name])  ❌ 명령어 인젝션 취약점!
#
# ==============================================================================

@bp.route('/api/simulator/status', methods=['GET'])
@handle_errors
def get_simulator_status():
    """
    Modbus 시뮬레이터 상태 조회

    Returns:
        JSON: 시뮬레이터 상태 정보
    """
    import subprocess

    try:
        # docker inspect 명령으로 시뮬레이터 상태 확인
        result = subprocess.run(
            ['docker', 'inspect', '-f', '{{.State.Running}}', 'modbus-simulator'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            return jsonify({
                'running': False,
                'status': 'stopped',
                'message': '시뮬레이터가 중지되어 있습니다'
            })

        is_running = result.stdout.strip() == 'true'

        return jsonify({
            'running': is_running,
            'status': 'running' if is_running else 'stopped',
            'container_name': 'modbus-simulator',
            'message': '시뮬레이터가 실행 중입니다' if is_running else '시뮬레이터가 중지되어 있습니다'
        })

    except subprocess.TimeoutExpired:
        return jsonify({
            'error': 'Timeout',
            'message': '시뮬레이터 상태 확인 시간 초과'
        }), 504
    except FileNotFoundError:
        return jsonify({
            'error': 'Docker not found',
            'message': 'Docker가 설치되어 있지 않습니다'
        }), 500
    except Exception as e:
        current_app.logger.error(f"Simulator status check error: {e}")
        return jsonify({
            'error': 'Status check failed',
            'message': str(e)
        }), 500


@bp.route('/api/simulator/start', methods=['POST'])
@require_api_key  # 인증 필수
@handle_errors
@rate_limit(max_requests=10, window=60)  # 1분에 10회로 제한
def start_simulator():
    """
    Modbus 시뮬레이터 시작

    인증 필요: X-API-Key 헤더 필수 (SIMULATOR_API_KEY 환경 변수 설정 시)

    Returns:
        JSON: 시작 결과
    """
    import subprocess

    try:
        result = subprocess.run(
            ['docker', 'start', 'modbus-simulator'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            current_app.logger.info("Simulator started successfully")
            return jsonify({
                'success': True,
                'message': '시뮬레이터가 시작되었습니다',
                'output': result.stdout
            })
        else:
            current_app.logger.error(f"Simulator start failed: {result.stderr}")
            return jsonify({
                'success': False,
                'error': 'Start failed',
                'message': '시뮬레이터 시작에 실패했습니다',
                'details': result.stderr
            }), 500

    except subprocess.TimeoutExpired:
        return jsonify({
            'error': 'Timeout',
            'message': '시뮬레이터 시작 시간 초과'
        }), 504
    except FileNotFoundError:
        return jsonify({
            'error': 'Docker not found',
            'message': 'Docker가 설치되어 있지 않습니다'
        }), 500


@bp.route('/api/simulator/stop', methods=['POST'])
@require_api_key  # 인증 필수
@handle_errors
@rate_limit(max_requests=10, window=60)  # 1분에 10회로 제한
def stop_simulator():
    """
    Modbus 시뮬레이터 중지

    인증 필요: X-API-Key 헤더 필수 (SIMULATOR_API_KEY 환경 변수 설정 시)

    Returns:
        JSON: 중지 결과
    """
    import subprocess

    try:
        result = subprocess.run(
            ['docker', 'stop', 'modbus-simulator'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            current_app.logger.info("Simulator stopped successfully")
            return jsonify({
                'success': True,
                'message': '시뮬레이터가 중지되었습니다',
                'output': result.stdout
            })
        else:
            current_app.logger.error(f"Simulator stop failed: {result.stderr}")
            return jsonify({
                'success': False,
                'error': 'Stop failed',
                'message': '시뮬레이터 중지에 실패했습니다',
                'details': result.stderr
            }), 500

    except subprocess.TimeoutExpired:
        return jsonify({
            'error': 'Timeout',
            'message': '시뮬레이터 중지 시간 초과'
        }), 504
    except FileNotFoundError:
        return jsonify({
            'error': 'Docker not found',
            'message': 'Docker가 설치되어 있지 않습니다'
        }), 500


@bp.route('/api/simulator/restart', methods=['POST'])
@require_api_key  # 인증 필수
@handle_errors
@rate_limit(max_requests=10, window=60)  # 1분에 10회로 제한
def restart_simulator():
    """
    Modbus 시뮬레이터 재시작

    인증 필요: X-API-Key 헤더 필수 (SIMULATOR_API_KEY 환경 변수 설정 시)

    Returns:
        JSON: 재시작 결과
    """
    import subprocess

    try:
        result = subprocess.run(
            ['docker', 'restart', 'modbus-simulator'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            current_app.logger.info("Simulator restarted successfully")
            return jsonify({
                'success': True,
                'message': '시뮬레이터가 재시작되었습니다',
                'output': result.stdout
            })
        else:
            current_app.logger.error(f"Simulator restart failed: {result.stderr}")
            return jsonify({
                'success': False,
                'error': 'Restart failed',
                'message': '시뮬레이터 재시작에 실패했습니다',
                'details': result.stderr
            }), 500

    except subprocess.TimeoutExpired:
        return jsonify({
            'error': 'Timeout',
            'message': '시뮬레이터 재시작 시간 초과'
        }), 504
    except FileNotFoundError:
        return jsonify({
            'error': 'Docker not found',
            'message': 'Docker가 설치되어 있지 않습니다'
        }), 500


# ==============================================================================
# Static 페이지 라우트 (UWB 하이패스 대시보드)
# ==============================================================================

@bp.route('/hipass')
def hipass_dashboard():
    """
    UWB 이륜차 하이패스 모니터링 대시보드

    레이저 센서 기반 입출차 감지 및 신호등 제어 전용 UI
    """
    from flask import send_file
    import os

    # static 폴더의 hipass.html 파일 경로
    hipass_path = os.path.join(current_app.root_path, 'static', 'hipass.html')

    if not os.path.exists(hipass_path):
        current_app.logger.error(f"hipass.html not found at: {hipass_path}")
        return jsonify({'error': 'Page not found'}), 404

    return send_file(hipass_path)


@bp.route('/api/hipass/config')
@handle_errors
@rate_limit(max_requests=60, window=60)  # 1분에 60회로 제한
def get_hipass_config():
    """
    하이패스 시스템 센서/신호등 매핑 설정 반환

    Returns:
        JSON: 하이패스 설정

    Raises:
        400: 설정 값이 유효하지 않은 경우
    """
    def safe_int(env_var: str, default: int, var_name: str) -> int:
        """환경 변수를 안전하게 정수로 변환"""
        try:
            value = int(os.getenv(env_var, str(default)))
            return value
        except ValueError:
            current_app.logger.warning(
                f"Invalid {var_name} in .env: {os.getenv(env_var)}, using default: {default}"
            )
            return default

    def validate_channel(value: int, var_name: str, min_val: int = 0, max_val: int = 3) -> int:
        """채널 번호 검증 (0-3 범위)

        Args:
            value: 검증할 채널 값
            var_name: 변수 이름 (에러 메시지용)
            min_val: 최소값 (기본값: 0)
            max_val: 최대값 (기본값: 3)

        Returns:
            int: 검증된 채널 값

        Raises:
            ValueError: 채널 값이 유효 범위를 벗어난 경우
        """
        if not min_val <= value <= max_val:
            error_msg = f"Invalid {var_name}: {value}, must be between {min_val} and {max_val}"
            current_app.logger.error(error_msg)
            raise ValueError(error_msg)
        return value

    try:
        # Lane 1 설정 로드 및 검증
        lane1_sensor1 = safe_int('HIPASS_LANE1_SENSOR1_DI', 1, 'LANE1_SENSOR1_DI')
        lane1_sensor2 = safe_int('HIPASS_LANE1_SENSOR2_DI', 3, 'LANE1_SENSOR2_DI')
        lane1_green = safe_int('HIPASS_LANE1_GREEN_DO', 0, 'LANE1_GREEN_DO')
        lane1_red = safe_int('HIPASS_LANE1_RED_DO', 1, 'LANE1_RED_DO')

        # Lane 2 설정 로드 및 검증
        lane2_sensor1 = safe_int('HIPASS_LANE2_SENSOR1_DI', 0, 'LANE2_SENSOR1_DI')
        lane2_sensor2 = safe_int('HIPASS_LANE2_SENSOR2_DI', 2, 'LANE2_SENSOR2_DI')
        lane2_green = safe_int('HIPASS_LANE2_GREEN_DO', 2, 'LANE2_GREEN_DO')
        lane2_red = safe_int('HIPASS_LANE2_RED_DO', 3, 'LANE2_RED_DO')

        # 채널 범위 검증
        validate_channel(lane1_sensor1, 'LANE1_SENSOR1_DI')
        validate_channel(lane1_sensor2, 'LANE1_SENSOR2_DI')
        validate_channel(lane1_green, 'LANE1_GREEN_DO')
        validate_channel(lane1_red, 'LANE1_RED_DO')
        validate_channel(lane2_sensor1, 'LANE2_SENSOR1_DI')
        validate_channel(lane2_sensor2, 'LANE2_SENSOR2_DI')
        validate_channel(lane2_green, 'LANE2_GREEN_DO')
        validate_channel(lane2_red, 'LANE2_RED_DO')

        config = {
            'lane1': {
                'sensor1_di': lane1_sensor1,
                'sensor2_di': lane1_sensor2,
                'green_do': lane1_green,
                'red_do': lane1_red
            },
            'lane2': {
                'sensor1_di': lane2_sensor1,
                'sensor2_di': lane2_sensor2,
                'green_do': lane2_green,
                'red_do': lane2_red
            },
            'invert_sensor_logic': os.getenv('HIPASS_INVERT_SENSOR_LOGIC', 'false').lower() == 'true'
        }

        return jsonify(config)

    except ValueError as e:
        # 채널 검증 실패 (400 Bad Request)
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        # 기타 서버 오류 (500 Internal Server Error)
        current_app.logger.error(f"Error loading hipass config: {e}")
        return jsonify({'error': 'Failed to load configuration'}), 500

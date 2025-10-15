"""
Flask API 라우트 (Secure Coding 표준 준수)

OWASP Secure Coding Practices를 적용한 REST API 및 SSE 엔드포인트
"""

import json
import time
from functools import wraps
from flask import Blueprint, jsonify, request, Response, current_app
from app import modbus_client, api_monitor_data
from app.validators import (
    ValidationError, validate_channel, validate_boolean,
    validate_json_payload, validate_device_id
)

# Blueprint 생성
bp = Blueprint('api', __name__)

# Rate limiting (간단한 구현)
_request_counts = {}
_RATE_LIMIT_WINDOW = 60  # 초
_RATE_LIMIT_MAX_REQUESTS = 100  # 분당 최대 요청 수


def rate_limit(max_requests=100, window=60):
    """
    Rate limiting 데코레이터

    Args:
        max_requests: 시간 창 내 최대 요청 수
        window: 시간 창 크기 (초)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 클라이언트 IP 가져오기
            client_ip = request.remote_addr

            # X-Forwarded-For 헤더 확인 (프록시 환경)
            if request.headers.get('X-Forwarded-For'):
                client_ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()

            current_time = time.time()

            # Rate limit 데이터 정리 (오래된 항목 제거)
            if client_ip in _request_counts:
                _request_counts[client_ip] = [
                    timestamp for timestamp in _request_counts[client_ip]
                    if current_time - timestamp < window
                ]
            else:
                _request_counts[client_ip] = []

            # Rate limit 확인
            if len(_request_counts[client_ip]) >= max_requests:
                current_app.logger.warning(
                    f"Rate limit exceeded: {client_ip} "
                    f"({len(_request_counts[client_ip])} requests in {window}s)"
                )
                return jsonify({
                    'error': '요청 한도를 초과했습니다',
                    'retry_after': window
                }), 429

            # 요청 기록
            _request_counts[client_ip].append(current_time)

            return func(*args, **kwargs)
        return wrapper
    return decorator


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
    헬스 체크 엔드포인트

    Returns:
        JSON: 서버 및 Modbus 연결 상태
    """
    status = modbus_client.get_status() if modbus_client else {
        'connected': False,
        'inputs': [False] * 4,
        'outputs': [False] * 4,
        'timestamp': 0
    }

    return jsonify({
        'status': 'healthy',
        'modbus_connected': status['connected']
    })


@bp.route('/api/status')
@handle_errors
@rate_limit(max_requests=60, window=60)
def get_status():
    """
    전체 입출력 상태 조회

    Returns:
        JSON: 연결 상태 및 입출력 상태
    """
    if not modbus_client:
        return jsonify({
            'error': 'Modbus client not initialized'
        }), 500

    status = modbus_client.get_status()

    # 민감한 정보 필터링 (프로덕션 환경에서)
    if current_app.config.get('FLASK_ENV') == 'production':
        if 'di_detection' in status and 'sensor_url' in status['di_detection']:
            # URL에서 호스트 부분만 남기고 경로는 마스킹
            url = status['di_detection']['sensor_url']
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                status['di_detection']['sensor_url'] = f"{parsed.scheme}://{parsed.netloc}/***"
            except:
                status['di_detection']['sensor_url'] = '***'

    return jsonify(status)


@bp.route('/api/output/<int:channel>', methods=['POST'])
@handle_errors
@rate_limit(max_requests=120, window=60)
def control_output(channel):
    """
    특정 출력 채널 제어

    Args:
        channel: 출력 채널 번호 (0-3)

    Body:
        {"state": true/false}

    Returns:
        JSON: 제어 결과
    """
    if not modbus_client:
        return jsonify({
            'error': 'Modbus client not initialized'
        }), 500

    # 채널 번호 검증
    try:
        channel = validate_channel(channel)
    except ValidationError as e:
        return jsonify({
            'error': 'Invalid channel',
            'message': str(e)
        }), 400

    # Content-Type 검증
    if not request.is_json:
        return jsonify({
            'error': 'Content-Type must be application/json'
        }), 415

    # 요청 본문 파싱 및 검증
    try:
        data = request.get_json()
        if data is None:
            raise ValidationError("요청 본문이 비어있습니다")

        validate_json_payload(data, required_fields=['state'])
        state = validate_boolean(data['state'])
    except ValidationError as e:
        return jsonify({
            'error': 'Invalid request body',
            'message': str(e)
        }), 400

    # 출력 제어
    success = modbus_client.write_output(channel, state)

    if success:
        current_app.logger.info(
            f"Output control: channel={channel}, state={state}, "
            f"client={request.remote_addr}"
        )
        return jsonify({
            'success': True,
            'channel': channel,
            'state': state
        })
    else:
        return jsonify({
            'error': 'Output control failed',
            'channel': channel
        }), 500


@bp.route('/api/output/<int:channel>/toggle', methods=['POST'])
@handle_errors
@rate_limit(max_requests=120, window=60)
def toggle_output(channel):
    """
    출력 채널 토글

    Args:
        channel: 출력 채널 번호 (0-3)

    Returns:
        JSON: 토글 결과 및 새로운 상태
    """
    if not modbus_client:
        return jsonify({
            'error': 'Modbus client not initialized'
        }), 500

    # 채널 번호 검증
    try:
        channel = validate_channel(channel)
    except ValidationError as e:
        return jsonify({
            'error': 'Invalid channel',
            'message': str(e)
        }), 400

    # 출력 토글
    success, new_state = modbus_client.toggle_output(channel)

    if success:
        current_app.logger.info(
            f"Output toggle: channel={channel}, new_state={new_state}, "
            f"client={request.remote_addr}"
        )
        return jsonify({
            'success': True,
            'channel': channel,
            'state': new_state
        })
    else:
        return jsonify({
            'error': 'Output toggle failed',
            'channel': channel
        }), 500


@bp.route('/api/config')
@handle_errors
@rate_limit(max_requests=10, window=60)
def get_config():
    """
    현재 Modbus 설정 조회

    Returns:
        JSON: Modbus 연결 설정 (민감한 정보는 마스킹)
    """
    if not modbus_client:
        return jsonify({
            'error': 'Modbus client not initialized'
        }), 500

    # 프로덕션 환경에서는 민감한 정보 마스킹
    if current_app.config.get('FLASK_ENV') == 'production':
        # IP 주소의 마지막 옥텟만 마스킹
        host = modbus_client.host
        host_parts = host.split('.')
        if len(host_parts) == 4:
            host_parts[-1] = '***'
            host = '.'.join(host_parts)
    else:
        host = modbus_client.host

    return jsonify({
        'modbus_host': host,
        'modbus_port': modbus_client.port,
        'modbus_unit_id': modbus_client.unit_id,
        'modbus_timeout': modbus_client.timeout,
        'poll_interval': modbus_client.poll_interval
    })


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

    current_app.logger.info(
        f"[Sensor Endpoint] DI detection received - "
        f"Device ID: {device_id}, DI States: [{di_states}], "
        f"Client: {request.remote_addr}"
    )

    return jsonify({
        'success': True,
        'message': 'DI detection received',
        'device_id': device_id,
        'di_states': di_states,
        'timestamp': time.time()
    })


@bp.route('/api/events')
@handle_errors
def sse_stream():
    """
    Server-Sent Events 스트림

    실시간 입출력 상태를 클라이언트에게 전송합니다.

    Returns:
        Response: SSE 스트림
    """
    def generate():
        """SSE 이벤트 생성기"""
        if not modbus_client:
            yield f"data: {json.dumps({'error': 'Modbus client not initialized'})}\n\n"
            return

        # 초기 상태 전송
        try:
            status = modbus_client.get_status()
            yield f"data: {json.dumps(status)}\n\n"
        except Exception as e:
            current_app.logger.error(f"SSE initial state error: {e}")
            yield f"data: {json.dumps({'error': 'Failed to get initial state'})}\n\n"
            return

        # 이전 상태 저장
        prev_status = status.copy()

        # 주기적으로 상태 확인 및 전송
        while True:
            try:
                time.sleep(0.2)  # 200ms 간격

                # 현재 상태 조회
                status = modbus_client.get_status()

                # 상태 변화가 있을 때만 전송 (효율성)
                if (status['inputs'] != prev_status['inputs'] or
                    status['outputs'] != prev_status['outputs'] or
                    status['connected'] != prev_status['connected'] or
                    status.get('di_detection', {}) != prev_status.get('di_detection', {})):

                    yield f"data: {json.dumps(status)}\n\n"
                    prev_status = status.copy()

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

"""
Flask API 라우트

REST API 및 SSE 엔드포인트를 제공합니다.
"""

import json
import time
from flask import Blueprint, jsonify, request, Response, current_app
from app import modbus_client, api_monitor_data

# Blueprint 생성
bp = Blueprint('api', __name__)


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
def get_status():
    """
    전체 입출력 상태 조회

    Returns:
        JSON: 연결 상태 및 입출력 상태
    """
    if not modbus_client:
        return jsonify({
            'error': 'Modbus 클라이언트가 초기화되지 않음'
        }), 500

    status = modbus_client.get_status()

    return jsonify({
        'connected': status['connected'],
        'inputs': status['inputs'],
        'outputs': status['outputs'],
        'timestamp': status['timestamp']
    })


@bp.route('/api/output/<int:channel>', methods=['POST'])
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
            'error': 'Modbus 클라이언트가 초기화되지 않음'
        }), 500

    # 채널 번호 유효성 검사
    if not 0 <= channel < 4:
        return jsonify({
            'error': f'잘못된 채널 번호: {channel} (0-3 범위여야 함)'
        }), 400

    # 요청 본문 파싱
    data = request.get_json()
    if not data or 'state' not in data:
        return jsonify({
            'error': '요청 본문에 "state" 필드가 필요함'
        }), 400

    state = bool(data['state'])

    # 출력 제어
    success = modbus_client.write_output(channel, state)

    if success:
        return jsonify({
            'success': True,
            'channel': channel,
            'state': state
        })
    else:
        return jsonify({
            'error': '출력 제어 실패',
            'channel': channel,
            'state': state
        }), 500


@bp.route('/api/output/<int:channel>/toggle', methods=['POST'])
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
            'error': 'Modbus 클라이언트가 초기화되지 않음'
        }), 500

    # 채널 번호 유효성 검사
    if not 0 <= channel < 4:
        return jsonify({
            'error': f'잘못된 채널 번호: {channel} (0-3 범위여야 함)'
        }), 400

    # 출력 토글
    success, new_state = modbus_client.toggle_output(channel)

    if success:
        return jsonify({
            'success': True,
            'channel': channel,
            'state': new_state
        })
    else:
        return jsonify({
            'error': '출력 토글 실패',
            'channel': channel
        }), 500


@bp.route('/api/config')
def get_config():
    """
    현재 Modbus 설정 조회

    Returns:
        JSON: Modbus 연결 설정
    """
    if not modbus_client:
        return jsonify({
            'error': 'Modbus 클라이언트가 초기화되지 않음'
        }), 500

    return jsonify({
        'modbus_host': modbus_client.host,
        'modbus_port': modbus_client.port,
        'modbus_unit_id': modbus_client.unit_id,
        'modbus_timeout': modbus_client.timeout,
        'poll_interval': modbus_client.poll_interval
    })


@bp.route('/api/monitor')
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


@bp.route('/api/events')
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
            yield f"data: {json.dumps({'error': 'Modbus 클라이언트가 초기화되지 않음'})}\n\n"
            return

        # 초기 상태 전송
        status = modbus_client.get_status()
        yield f"data: {json.dumps(status)}\n\n"

        # 이전 상태 저장
        prev_status = status.copy()

        # 주기적으로 상태 확인 및 전송
        while True:
            try:
                time.sleep(0.2)  # 200ms 간격 (부하 감소)

                # 현재 상태 조회
                status = modbus_client.get_status()

                # 상태 변화가 있을 때만 전송 (효율성)
                if (status['inputs'] != prev_status['inputs'] or
                    status['outputs'] != prev_status['outputs'] or
                    status['connected'] != prev_status['connected']):

                    yield f"data: {json.dumps(status)}\n\n"
                    prev_status = status.copy()

            except GeneratorExit:
                # 클라이언트 연결 끊김 (로깅 생략, 정상 동작)
                break
            except Exception as e:
                # 에러 발생 시에만 전송
                try:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                except:
                    pass
                break

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


@bp.errorhandler(404)
def not_found(error):
    """404 오류 핸들러"""
    return jsonify({
        'error': '요청한 리소스를 찾을 수 없음'
    }), 404


@bp.errorhandler(500)
def internal_error(error):
    """500 오류 핸들러"""
    current_app.logger.error(f"내부 서버 오류: {error}")
    return jsonify({
        'error': '내부 서버 오류'
    }), 500

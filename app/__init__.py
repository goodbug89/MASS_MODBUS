"""
Flask 애플리케이션 팩토리

애플리케이션 초기화 및 설정을 담당합니다.
"""

import logging
import time
from collections import deque
from flask import Flask
from config.config import get_config
from app.modbus_client import CIE_H14A_Client

# 전역 Modbus 클라이언트 인스턴스 (중요: 단일 연결 유지)
modbus_client: CIE_H14A_Client = None

# API 모니터링 데이터 (최근 100개 기록)
api_monitor_data = {
    'history': deque(maxlen=100),  # 최근 100개 요청 기록
    'start_time': time.time(),
    'total_requests': 0,
    'failed_requests': 0,
    'last_health_check': None
}


def create_app(config_name: str = None) -> Flask:
    """
    Flask 애플리케이션 팩토리

    Args:
        config_name: 설정 환경 이름 (development, production, test)

    Returns:
        Flask: 설정된 Flask 애플리케이션
    """
    app = Flask(__name__, static_folder='static', static_url_path='')

    # 설정 로드
    config = get_config(config_name)
    app.config.from_object(config)

    # 로깅 설정
    setup_logging(app)

    # Modbus 클라이언트 초기화
    init_modbus_client(app)

    # 라우트 등록
    register_routes(app)

    # 애플리케이션 이벤트 핸들러
    register_app_handlers(app)

    app.logger.info(f"Flask 애플리케이션 초기화 완료: {config_name or 'default'} 환경")

    return app


def setup_logging(app: Flask) -> None:
    """
    로깅 설정

    Args:
        app: Flask 애플리케이션
    """
    log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO'))
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    app.logger.setLevel(log_level)


def init_modbus_client(app: Flask) -> None:
    """
    Modbus 클라이언트 초기화

    전역 modbus_client 인스턴스를 생성하고 연결합니다.
    중요: 단일 Modbus 연결만 유지해야 합니다.

    Args:
        app: Flask 애플리케이션
    """
    global modbus_client

    app.logger.info("Modbus 클라이언트 초기화 중...")

    modbus_client = CIE_H14A_Client(
        host=app.config['MODBUS_HOST'],
        port=app.config['MODBUS_PORT'],
        unit_id=app.config['MODBUS_UNIT_ID'],
        timeout=app.config['MODBUS_TIMEOUT'],
        poll_interval=app.config['POLL_INTERVAL'],
        auto_off_time=app.config['OUTPUT_AUTO_OFF_TIME'],
        retry_count=app.config['OUTPUT_RETRY_COUNT'],
        retry_delay=app.config['OUTPUT_RETRY_DELAY']
    )

    # 연결 시도
    if modbus_client.connect():
        app.logger.info(
            f"Modbus 연결 성공: {app.config['MODBUS_HOST']}:{app.config['MODBUS_PORT']}"
        )
        # 백그라운드 폴링 시작
        modbus_client.start_polling()
        app.logger.info("Modbus 폴링 시작")
    else:
        app.logger.warning(
            f"Modbus 초기 연결 실패: {app.config['MODBUS_HOST']}:{app.config['MODBUS_PORT']} "
            "(재연결은 자동으로 시도됩니다)"
        )
        # 연결 실패해도 폴링 시작 (자동 재연결 시도)
        modbus_client.start_polling()


def register_routes(app: Flask) -> None:
    """
    라우트 등록

    Args:
        app: Flask 애플리케이션
    """
    from app.routes import bp
    app.register_blueprint(bp)
    app.logger.info("라우트 등록 완료")


def register_app_handlers(app: Flask) -> None:
    """
    애플리케이션 이벤트 핸들러 등록

    Args:
        app: Flask 애플리케이션
    """

    @app.before_request
    def before_request():
        """요청 전 처리"""
        from flask import request, g
        g.start_time = time.time()
        g.request_path = request.path

    @app.after_request
    def after_request(response):
        """요청 후 처리: CORS 헤더 추가 및 모니터링"""
        from flask import g

        # CORS 헤더
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')

        # API 모니터링 (health check 제외)
        if hasattr(g, 'start_time') and hasattr(g, 'request_path'):
            if g.request_path != '/health' and not g.request_path.startswith('/css') and not g.request_path.startswith('/js'):
                duration = time.time() - g.start_time
                api_monitor_data['total_requests'] += 1

                is_success = 200 <= response.status_code < 400
                if not is_success:
                    api_monitor_data['failed_requests'] += 1

                api_monitor_data['history'].append({
                    'timestamp': time.time(),
                    'path': g.request_path,
                    'status': response.status_code,
                    'duration': round(duration * 1000, 2),  # ms
                    'success': is_success
                })

        return response

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        """애플리케이션 컨텍스트 종료 시 처리"""
        pass


def shutdown_modbus_client():
    """
    Modbus 클라이언트 종료

    애플리케이션 종료 시 호출되어야 합니다.
    """
    global modbus_client
    if modbus_client:
        logging.info("Modbus 클라이언트 종료 중...")
        modbus_client.stop_polling()
        modbus_client.disconnect()
        logging.info("Modbus 클라이언트 종료 완료")


# 애플리케이션 종료 시 정리
import atexit
atexit.register(shutdown_modbus_client)

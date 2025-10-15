"""
Flask 애플리케이션 팩토리

멀티 디바이스 지원 - 최대 8대의 CIE-H14A 장비를 동시 제어합니다.
"""

import logging
import time
from collections import deque
from typing import Dict
from flask import Flask
from config.config import get_config
from app.modbus_client import CIE_H14A_Client

# 전역 Modbus 클라이언트 딕셔너리 (멀티 디바이스 지원)
# Key: device_id (예: 'device1', 'device2', ...)
# Value: CIE_H14A_Client 인스턴스
modbus_clients: Dict[str, CIE_H14A_Client] = {}

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

    # 장비 설정 초기화
    devices_config = config.init_devices_config()
    app.config['DEVICES'] = devices_config  # Flask app config에 명시적으로 설정

    # 로깅 설정
    setup_logging(app)

    # 설정 검증
    try:
        config.validate_devices_config()
    except ValueError as e:
        app.logger.error(f"Configuration validation failed: {e}")
        raise

    # Modbus 클라이언트 초기화 (멀티 디바이스)
    init_modbus_clients(app)

    # 라우트 등록
    register_routes(app)

    # 애플리케이션 이벤트 핸들러
    register_app_handlers(app)

    app.logger.info(f"Flask application initialized: {config_name or 'default'} environment")

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


def init_modbus_clients(app: Flask) -> None:
    """
    Modbus 클라이언트 초기화 (멀티 디바이스)

    전역 modbus_clients 딕셔너리에 각 장비의 클라이언트를 생성하고 연결합니다.
    각 장비는 독립적인 스레드에서 폴링합니다.

    Args:
        app: Flask 애플리케이션
    """
    global modbus_clients

    app.logger.info("Initializing Modbus clients (multi-device)...")

    devices_config = app.config['DEVICES']

    if not devices_config:
        app.logger.error("No devices configured!")
        raise ValueError("No devices configured. Please check .env file.")

    success_count = 0

    for device_id, device_config in devices_config.items():
        app.logger.info(
            f"[{device_id}] Initializing {device_config['name']} "
            f"({device_config['host']}:{device_config['port']})..."
        )

        # CIE_H14A_Client 인스턴스 생성
        client = CIE_H14A_Client(
            host=device_config['host'],
            port=device_config['port'],
            unit_id=device_config['unit_id'],
            timeout=device_config['timeout'],
            poll_interval=device_config['poll_interval'],
            auto_off_time=device_config['auto_off_time'],
            retry_count=device_config['retry_count'],
            retry_delay=device_config['retry_delay'],
            sensor_url=device_config.get('sensor_url'),
            sensor_device_id=device_id  # 장비 ID를 전달 (DI 감지 시 사용)
        )

        # 연결 시도
        if client.connect():
            app.logger.info(
                f"[{device_id}] Modbus connection successful: "
                f"{device_config['host']}:{device_config['port']}"
            )
            success_count += 1
        else:
            app.logger.warning(
                f"[{device_id}] Modbus initial connection failed "
                f"(auto-reconnect will be attempted)"
            )

        # 폴링 시작 (연결 실패해도 자동 재연결 시도)
        client.start_polling()
        app.logger.info(f"[{device_id}] Polling started")

        # 클라이언트 등록
        modbus_clients[device_id] = client

    app.logger.info(
        f"Modbus clients initialization complete: "
        f"{success_count}/{len(devices_config)} devices connected"
    )


def register_routes(app: Flask) -> None:
    """
    라우트 등록

    Args:
        app: Flask 애플리케이션
    """
    from app.routes import bp
    app.register_blueprint(bp)
    app.logger.info("Routes registered")


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
        """요청 후 처리: 보안 헤더, CORS, 모니터링"""
        from flask import g

        # 보안 헤더 추가 (OWASP Secure Headers)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        # CSP (Content Security Policy) - 개발 환경에서는 느슨하게, 프로덕션에서는 엄격하게
        if app.config.get('FLASK_ENV') == 'production':
            response.headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data:; "
                "font-src 'self' https://cdn.jsdelivr.net; "
                "connect-src 'self'; "
                "frame-ancestors 'none'"
            )

        # 서버 정보 숨기기
        response.headers.pop('Server', None)

        # CORS 헤더 (프로덕션에서는 특정 origin만 허용해야 함)
        allowed_origins = app.config.get('ALLOWED_ORIGINS', '*')
        response.headers['Access-Control-Allow-Origin'] = allowed_origins
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
        response.headers['Access-Control-Max-Age'] = '3600'

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


def shutdown_modbus_clients():
    """
    Modbus 클라이언트 종료 (멀티 디바이스)

    애플리케이션 종료 시 호출되어 모든 장비의 연결을 종료합니다.
    """
    global modbus_clients

    if modbus_clients:
        logging.info("Shutting down Modbus clients...")

        for device_id, client in modbus_clients.items():
            logging.info(f"[{device_id}] Stopping polling...")
            client.stop_polling()

            logging.info(f"[{device_id}] Disconnecting...")
            client.disconnect()

            logging.info(f"[{device_id}] Shutdown complete")

        modbus_clients.clear()
        logging.info("All Modbus clients shutdown complete")


# 애플리케이션 종료 시 정리
import atexit
atexit.register(shutdown_modbus_clients)

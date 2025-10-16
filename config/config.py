"""
Flask 애플리케이션 설정

환경 변수를 통해 설정을 관리합니다.
멀티 디바이스 지원: DEVICE1~8까지 최대 8대 장비 설정 가능
"""

import os
import re
from dotenv import load_dotenv
from typing import Dict, Any

# .env 파일 로드
load_dotenv()


class Config:
    """기본 설정"""

    # Flask 설정
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    FLASK_ENV = os.getenv('FLASK_ENV', 'production')

    # ===========================================================================
    # Modbus 전역 기본값 (개별 장비 설정이 없을 때 사용)
    # ===========================================================================
    MODBUS_DEFAULT_UNIT_ID = int(os.getenv('MODBUS_DEFAULT_UNIT_ID', 1))
    MODBUS_DEFAULT_TIMEOUT = float(os.getenv('MODBUS_DEFAULT_TIMEOUT', 0.3))
    MODBUS_DEFAULT_POLL_INTERVAL = float(os.getenv('MODBUS_DEFAULT_POLL_INTERVAL', 0.5))
    MODBUS_DEFAULT_AUTO_OFF_TIME = float(os.getenv('MODBUS_DEFAULT_AUTO_OFF_TIME', 1.0))
    MODBUS_DEFAULT_RETRY_COUNT = int(os.getenv('MODBUS_DEFAULT_RETRY_COUNT', 3))
    MODBUS_DEFAULT_RETRY_DELAY = float(os.getenv('MODBUS_DEFAULT_RETRY_DELAY', 0.1))

    # 센서 URL (DI 감지 시 호출할 URL)
    SENSOR_URL = os.getenv('SENSOR_URL')  # 예: http://localhost:5000/api/get_sensor

    # ===========================================================================
    # 멀티 디바이스 설정
    # ===========================================================================
    DEVICES: Dict[str, Dict[str, Any]] = {}

    # 로깅 설정
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

    @classmethod
    def init_devices_config(cls) -> Dict[str, Dict[str, Any]]:
        """
        환경 변수에서 장비 설정 파싱

        환경 변수 형식:
            DEVICE1_ENABLED=true
            DEVICE1_NAME=Lane1
            DEVICE1_HOST=192.168.10.101
            DEVICE1_PORT=502             # 선택 (기본값: MODBUS_DEFAULT_PORT)
            DEVICE1_UNIT_ID=1            # 선택 (기본값: MODBUS_DEFAULT_UNIT_ID)
            ...

        Returns:
            Dict[str, Dict[str, Any]]: 장비 설정 딕셔너리
                {
                    'device1': {
                        'name': 'Lane1',
                        'host': '192.168.10.101',
                        'port': 502,
                        'unit_id': 1,
                        'timeout': 0.3,
                        'poll_interval': 0.5,
                        'auto_off_time': 1.0,
                        'retry_count': 3,
                        'retry_delay': 0.1,
                        'sensor_url': 'http://localhost:5000/api/get_sensor'
                    },
                    ...
                }
        """
        devices = {}

        for i in range(1, 9):  # 최대 8대까지 지원
            device_id = f'device{i}'
            enabled_key = f'DEVICE{i}_ENABLED'

            # 장비가 활성화되어 있는지 확인
            enabled = os.getenv(enabled_key, 'false').lower()
            if enabled not in ['true', '1', 'yes']:
                continue

            # 필수 항목: HOST
            host = os.getenv(f'DEVICE{i}_HOST')
            if not host:
                print(f"[WARNING] DEVICE{i}_HOST is not set - Skipping device {i}")
                continue

            # 장비 설정 구성 (기본값 + 개별 설정 오버라이드)
            devices[device_id] = {
                'name': os.getenv(f'DEVICE{i}_NAME', f'Device{i}'),
                'host': host,
                'port': int(os.getenv(f'DEVICE{i}_PORT', 502)),  # PORT는 필수 (기본값: 502)
                'unit_id': int(os.getenv(f'DEVICE{i}_UNIT_ID', cls.MODBUS_DEFAULT_UNIT_ID)),
                'timeout': float(os.getenv(f'DEVICE{i}_TIMEOUT', cls.MODBUS_DEFAULT_TIMEOUT)),
                'poll_interval': float(os.getenv(f'DEVICE{i}_POLL_INTERVAL', cls.MODBUS_DEFAULT_POLL_INTERVAL)),
                'auto_off_time': float(os.getenv(f'DEVICE{i}_AUTO_OFF_TIME', cls.MODBUS_DEFAULT_AUTO_OFF_TIME)),
                'retry_count': int(os.getenv(f'DEVICE{i}_RETRY_COUNT', cls.MODBUS_DEFAULT_RETRY_COUNT)),
                'retry_delay': float(os.getenv(f'DEVICE{i}_RETRY_DELAY', cls.MODBUS_DEFAULT_RETRY_DELAY)),
                'sensor_url': os.getenv(f'DEVICE{i}_SENSOR_URL', cls.SENSOR_URL)
            }

        cls.DEVICES = devices
        return devices

    @classmethod
    def validate_devices_config(cls) -> bool:
        """
        장비 설정 유효성 검증

        Raises:
            ValueError: 설정이 유효하지 않은 경우

        Returns:
            bool: 검증 성공 여부
        """
        if not cls.DEVICES:
            raise ValueError(
                "No devices configured. Please set at least one device "
                "(e.g., DEVICE1_ENABLED=true, DEVICE1_HOST=192.168.10.101)"
            )

        ip_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')

        for device_id, config in cls.DEVICES.items():
            # 필수 항목 확인
            if 'host' not in config or not config['host']:
                raise ValueError(f"{device_id}: HOST is required")

            # IP 형식 검증 (간단한 정규식)
            if not ip_pattern.match(config['host']):
                # IP가 아니면 호스트명일 수 있음 (localhost, domain 등)
                if config['host'] not in ['localhost', '127.0.0.1']:
                    # 간단한 검증만 수행
                    pass

            # 포트 범위 확인
            if not (1 <= config['port'] <= 65535):
                raise ValueError(
                    f"{device_id}: Invalid port number - {config['port']} "
                    "(must be 1-65535)"
                )

            # Unit ID 범위 확인
            if not (0 <= config['unit_id'] <= 255):
                raise ValueError(
                    f"{device_id}: Invalid unit_id - {config['unit_id']} "
                    "(must be 0-255)"
                )

            # Timeout 범위 확인
            if not (0.1 <= config['timeout'] <= 60.0):
                raise ValueError(
                    f"{device_id}: Invalid timeout - {config['timeout']} "
                    "(must be 0.1-60.0 seconds)"
                )

        print(f"[OK] Device configuration validated: {len(cls.DEVICES)} devices")
        return True


class DevelopmentConfig(Config):
    """개발 환경 설정"""
    DEBUG = True
    FLASK_ENV = 'development'


class ProductionConfig(Config):
    """프로덕션 환경 설정"""
    DEBUG = False
    FLASK_ENV = 'production'


class TestConfig(Config):
    """테스트 환경 설정"""
    TESTING = True
    MODBUS_HOST = '127.0.0.1'  # 테스트용 로컬 시뮬레이터


# 환경별 설정 매핑
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'test': TestConfig,
    'default': ProductionConfig
}


def get_config(env_name: str = None) -> Config:
    """
    환경 이름에 따른 설정 객체 반환

    Args:
        env_name: 환경 이름 (development, production, test)

    Returns:
        Config: 설정 객체
    """
    if env_name is None:
        env_name = os.getenv('FLASK_ENV', 'production')

    return config_by_name.get(env_name, ProductionConfig)

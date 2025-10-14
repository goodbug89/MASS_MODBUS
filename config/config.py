"""
Flask 애플리케이션 설정

환경 변수를 통해 설정을 관리합니다.
"""

import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()


class Config:
    """기본 설정"""

    # Flask 설정
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    FLASK_ENV = os.getenv('FLASK_ENV', 'production')

    # Modbus TCP 설정
    MODBUS_HOST = os.getenv('MODBUS_HOST', '10.1.0.1')
    MODBUS_PORT = int(os.getenv('MODBUS_PORT', 502))
    MODBUS_UNIT_ID = int(os.getenv('MODBUS_UNIT_ID', 1))
    MODBUS_TIMEOUT = float(os.getenv('MODBUS_TIMEOUT', 5.0))

    # 폴링 설정
    POLL_INTERVAL = float(os.getenv('POLL_INTERVAL', 0.5))

    # DO 출력 자동 꺼짐 시간 (초 단위, 0이면 비활성화)
    OUTPUT_AUTO_OFF_TIME = float(os.getenv('OUTPUT_AUTO_OFF_TIME', 1.0))

    # DO 출력 제어 재시도 설정
    OUTPUT_RETRY_COUNT = int(os.getenv('OUTPUT_RETRY_COUNT', 3))
    OUTPUT_RETRY_DELAY = float(os.getenv('OUTPUT_RETRY_DELAY', 0.1))

    # 로깅 설정
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')


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

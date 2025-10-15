"""
입력 검증 및 Sanitization 유틸리티

OWASP Secure Coding 표준을 준수하는 입력 검증 함수들
"""

import re
from typing import Any, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """입력 검증 실패 시 발생하는 예외"""
    pass


def sanitize_string(value: Any, max_length: int = 255, allow_pattern: str = r'^[a-zA-Z0-9_\-\.]+$') -> str:
    """
    문자열 sanitization

    Args:
        value: 검증할 값
        max_length: 최대 길이
        allow_pattern: 허용할 정규식 패턴

    Returns:
        str: Sanitize된 문자열

    Raises:
        ValidationError: 검증 실패 시
    """
    if not isinstance(value, str):
        value = str(value)

    # 길이 검증
    if len(value) > max_length:
        raise ValidationError(f"문자열 길이가 최대값({max_length})을 초과합니다")

    # 패턴 검증
    if not re.match(allow_pattern, value):
        raise ValidationError(f"허용되지 않은 문자가 포함되어 있습니다")

    # XSS 방지를 위한 HTML 태그 제거
    value = re.sub(r'<[^>]*>', '', value)

    return value.strip()


def validate_channel(channel: Any) -> int:
    """
    채널 번호 검증 (0-3)

    Args:
        channel: 검증할 채널 번호

    Returns:
        int: 검증된 채널 번호

    Raises:
        ValidationError: 검증 실패 시
    """
    try:
        channel_int = int(channel)
    except (ValueError, TypeError):
        raise ValidationError(f"채널 번호는 정수여야 합니다: {channel}")

    if not 0 <= channel_int < 4:
        raise ValidationError(f"채널 번호는 0-3 범위여야 합니다: {channel_int}")

    return channel_int


def validate_boolean(value: Any) -> bool:
    """
    Boolean 값 검증

    Args:
        value: 검증할 값

    Returns:
        bool: 검증된 Boolean 값

    Raises:
        ValidationError: 검증 실패 시
    """
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        value_lower = value.lower()
        if value_lower in ('true', '1', 'yes', 'on'):
            return True
        elif value_lower in ('false', '0', 'no', 'off'):
            return False

    if isinstance(value, (int, float)):
        return bool(value)

    raise ValidationError(f"Boolean 값으로 변환할 수 없습니다: {value}")


def validate_device_id(device_id: Any) -> str:
    """
    장비 ID 검증

    Args:
        device_id: 검증할 장비 ID

    Returns:
        str: 검증된 장비 ID

    Raises:
        ValidationError: 검증 실패 시
    """
    # 영문자, 숫자, 언더스코어, 하이픈만 허용
    return sanitize_string(device_id, max_length=50, allow_pattern=r'^[a-zA-Z0-9_\-]+$')


def validate_url(url: Any) -> str:
    """
    URL 검증 (SSRF 방지)

    Args:
        url: 검증할 URL

    Returns:
        str: 검증된 URL

    Raises:
        ValidationError: 검증 실패 시
    """
    if not isinstance(url, str):
        raise ValidationError("URL은 문자열이어야 합니다")

    url = url.strip()

    # 길이 검증
    if len(url) > 2048:
        raise ValidationError("URL 길이가 너무 깁니다")

    # 기본 URL 형식 검증
    url_pattern = r'^https?://[a-zA-Z0-9\-\.]+(:[0-9]+)?(/[a-zA-Z0-9\-\._~:/?#\[\]@!$&\'()*+,;=%]*)?$'
    if not re.match(url_pattern, url):
        raise ValidationError("잘못된 URL 형식입니다")

    # SSRF 방지: 로컬호스트와 사설 IP 대역 차단 (production 환경에서)
    blocked_patterns = [
        r'://localhost[:/]',
        r'://127\.',
        r'://10\.',
        r'://192\.168\.',
        r'://172\.(1[6-9]|2[0-9]|3[0-1])\.',
        r'://169\.254\.',
        r'://0\.',
    ]

    for pattern in blocked_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            # 개발 환경에서만 localhost 허용
            import os
            if os.getenv('FLASK_ENV') != 'development':
                raise ValidationError("내부 네트워크 URL은 허용되지 않습니다")

    return url


def validate_json_payload(data: dict, required_fields: list, optional_fields: list = None) -> dict:
    """
    JSON payload 검증

    Args:
        data: 검증할 데이터
        required_fields: 필수 필드 목록
        optional_fields: 선택 필드 목록

    Returns:
        dict: 검증된 데이터

    Raises:
        ValidationError: 검증 실패 시
    """
    if not isinstance(data, dict):
        raise ValidationError("JSON 객체여야 합니다")

    # 필수 필드 검증
    for field in required_fields:
        if field not in data:
            raise ValidationError(f"필수 필드가 누락되었습니다: {field}")

    # 허용되지 않은 필드 확인
    allowed_fields = set(required_fields)
    if optional_fields:
        allowed_fields.update(optional_fields)

    unexpected_fields = set(data.keys()) - allowed_fields
    if unexpected_fields:
        raise ValidationError(f"허용되지 않은 필드: {', '.join(unexpected_fields)}")

    return data


def validate_ip_address(ip: str) -> str:
    """
    IP 주소 검증

    Args:
        ip: 검증할 IP 주소

    Returns:
        str: 검증된 IP 주소

    Raises:
        ValidationError: 검증 실패 시
    """
    if not isinstance(ip, str):
        raise ValidationError("IP 주소는 문자열이어야 합니다")

    # IPv4 형식 검증
    ipv4_pattern = r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'
    match = re.match(ipv4_pattern, ip)

    if not match:
        raise ValidationError(f"잘못된 IP 주소 형식입니다: {ip}")

    # 각 옥텟이 0-255 범위인지 확인
    for octet in match.groups():
        if int(octet) > 255:
            raise ValidationError(f"잘못된 IP 주소입니다: {ip}")

    return ip


def validate_port(port: Any) -> int:
    """
    포트 번호 검증

    Args:
        port: 검증할 포트 번호

    Returns:
        int: 검증된 포트 번호

    Raises:
        ValidationError: 검증 실패 시
    """
    try:
        port_int = int(port)
    except (ValueError, TypeError):
        raise ValidationError(f"포트 번호는 정수여야 합니다: {port}")

    if not 1 <= port_int <= 65535:
        raise ValidationError(f"포트 번호는 1-65535 범위여야 합니다: {port_int}")

    return port_int


def validate_timeout(timeout: Any) -> float:
    """
    타임아웃 값 검증

    Args:
        timeout: 검증할 타임아웃 값 (초)

    Returns:
        float: 검증된 타임아웃 값

    Raises:
        ValidationError: 검증 실패 시
    """
    try:
        timeout_float = float(timeout)
    except (ValueError, TypeError):
        raise ValidationError(f"타임아웃 값은 숫자여야 합니다: {timeout}")

    if not 0.1 <= timeout_float <= 60.0:
        raise ValidationError(f"타임아웃 값은 0.1-60.0 범위여야 합니다: {timeout_float}")

    return timeout_float

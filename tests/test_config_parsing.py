#!/usr/bin/env python3
"""
설정 파일 파싱 테스트

멀티 디바이스 설정이 올바르게 파싱되는지 테스트합니다.
"""

import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.config import Config


def test_config_parsing():
    """설정 파싱 테스트"""
    print("=" * 80)
    print(">> 멀티 디바이스 설정 파싱 테스트")
    print("=" * 80)

    # 1. 장비 설정 초기화
    print("\n[1] Initializing device configuration...")
    devices = Config.init_devices_config()

    print(f"\n[OK] Found {len(devices)} devices\n")

    # 2. 장비 목록 출력
    print("=" * 80)
    print(">> Device Configuration")
    print("=" * 80)

    for device_id, config in devices.items():
        print(f"\n[{device_id}]")
        print(f"  Name:          {config['name']}")
        print(f"  Host:          {config['host']}")
        print(f"  Port:          {config['port']}")
        print(f"  Unit ID:       {config['unit_id']}")
        print(f"  Timeout:       {config['timeout']}s")
        print(f"  Poll Interval: {config['poll_interval']}s")
        print(f"  Auto-Off Time: {config['auto_off_time']}s")
        print(f"  Retry Count:   {config['retry_count']}")
        print(f"  Retry Delay:   {config['retry_delay']}s")
        print(f"  Sensor URL:    {config['sensor_url']}")

    # 3. 설정 검증
    print("\n" + "=" * 80)
    print(">> Validating Configuration")
    print("=" * 80 + "\n")

    try:
        Config.validate_devices_config()
        print("\n[OK] Configuration validation passed!")
    except ValueError as e:
        print(f"\n[ERROR] Configuration validation failed: {e}")
        return False

    # 4. 요약 정보
    print("\n" + "=" * 80)
    print(">> Summary")
    print("=" * 80)
    print(f"  Total Devices:  {len(devices)}")
    print(f"  Device IDs:     {', '.join(devices.keys())}")
    print(f"  Device Names:   {', '.join(c['name'] for c in devices.values())}")
    print("=" * 80 + "\n")

    return True


if __name__ == '__main__':
    success = test_config_parsing()
    sys.exit(0 if success else 1)

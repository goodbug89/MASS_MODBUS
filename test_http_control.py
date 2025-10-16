#!/usr/bin/env python3
"""
HTTP API를 통한 장비 제어 테스트

Usage:
    python test_http_control.py
"""

import requests
import time

BASE_URL = "http://localhost:5000"

def test_device_control(device_id: str, channel: int):
    """장비 제어 테스트"""
    print(f"\n{'='*60}")
    print(f"테스트: {device_id} - DO{channel} 제어")
    print(f"{'='*60}")

    # 1. DO ON
    print(f"\n[1] DO{channel} ON 명령...")
    url = f"{BASE_URL}/api/devices/{device_id}/output/{channel}"
    response = requests.post(
        url,
        json={"state": True},
        headers={"Content-Type": "application/json"}
    )

    print(f"   Status Code: {response.status_code}")
    print(f"   Response: {response.json()}")

    if response.status_code == 200:
        print(f"[OK] DO{channel} ON 성공")
    else:
        print(f"[FAIL] DO{channel} ON 실패")
        return False

    time.sleep(2)

    # 2. DO OFF
    print(f"\n[2] DO{channel} OFF 명령...")
    response = requests.post(
        url,
        json={"state": False},
        headers={"Content-Type": "application/json"}
    )

    print(f"   Status Code: {response.status_code}")
    print(f"   Response: {response.json()}")

    if response.status_code == 200:
        print(f"[OK] DO{channel} OFF 성공")
    else:
        print(f"[FAIL] DO{channel} OFF 실패")
        return False

    time.sleep(1)

    # 3. Toggle (추가 테스트)
    print(f"\n[3] DO{channel} TOGGLE 명령...")
    toggle_url = f"{url}/toggle"
    response = requests.post(toggle_url)

    print(f"   Status Code: {response.status_code}")
    print(f"   Response: {response.json()}")

    if response.status_code == 200:
        print(f"[OK] DO{channel} TOGGLE 성공")
        result = response.json()
        print(f"   새로운 상태: {'ON' if result.get('state') else 'OFF'}")
    else:
        print(f"[FAIL] DO{channel} TOGGLE 실패")

    return True


def test_device_status(device_id: str):
    """장비 상태 조회"""
    print(f"\n[상태 조회] {device_id}")
    url = f"{BASE_URL}/api/devices/{device_id}/status"
    response = requests.get(url)

    if response.status_code == 200:
        status = response.json()
        print(f"   연결 상태: {'연결됨' if status.get('connected') else '연결 끊김'}")
        print(f"   DI 상태: {status.get('inputs')}")
        print(f"   DO 상태: {status.get('outputs')}")
    else:
        print(f"   [FAIL] 상태 조회 실패: {response.status_code}")


def main():
    """메인 함수"""
    print("\n" + "="*60)
    print("HTTP API를 통한 장비 제어 테스트")
    print("="*60)

    # 장비 목록 조회
    print("\n[장비 목록 조회]")
    try:
        response = requests.get(f"{BASE_URL}/api/devices")
        if response.status_code == 200:
            devices = response.json().get('devices', [])
            print(f"활성화된 장비: {len(devices)}대")
            for device in devices:
                print(f"  - {device['id']}: {device['name']} ({device['host']})")
        else:
            print(f"[FAIL] 장비 목록 조회 실패: {response.status_code}")
            return
    except requests.exceptions.ConnectionError:
        print("[ERROR] 서버에 연결할 수 없습니다. Flask 앱이 실행 중인지 확인하세요.")
        return

    # device2, DO1 제어 테스트
    device_id = "device2"
    channel = 1

    print(f"\n{'='*60}")
    print(f"테스트 대상: {device_id}, DO{channel}")
    print(f"{'='*60}")

    # 초기 상태 확인
    test_device_status(device_id)

    # 제어 테스트
    success = test_device_control(device_id, channel)

    # 최종 상태 확인
    test_device_status(device_id)

    # 결과 요약
    print("\n" + "="*60)
    print("테스트 완료")
    print("="*60)

    if success:
        print("[OK] 모든 테스트 성공")
    else:
        print("[FAIL] 일부 테스트 실패")

    print("\n올바른 API 사용법:")
    print("-"*60)
    print("1. DO ON:")
    print(f"   curl -X POST {BASE_URL}/api/devices/{device_id}/output/{channel} \\")
    print('        -H "Content-Type: application/json" \\')
    print('        -d \'{"state": true}\'')
    print()
    print("2. DO OFF:")
    print(f"   curl -X POST {BASE_URL}/api/devices/{device_id}/output/{channel} \\")
    print('        -H "Content-Type: application/json" \\')
    print('        -d \'{"state": false}\'')
    print()
    print("3. DO TOGGLE:")
    print(f"   curl -X POST {BASE_URL}/api/devices/{device_id}/output/{channel}/toggle")
    print("="*60 + "\n")


if __name__ == '__main__':
    main()

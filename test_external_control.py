#!/usr/bin/env python3
"""
도커 외부에서 시뮬레이터 DO 제어 테스트

Usage:
    python test_external_control.py
"""

from pyModbusTCP.client import ModbusClient
import time

def test_do_control(device_name: str, host: str, port: int):
    """DO 제어 테스트"""
    print(f"\n{'='*60}")
    print(f"테스트: {device_name} ({host}:{port})")
    print(f"{'='*60}")

    client = ModbusClient(host=host, port=port, timeout=2.0)

    try:
        if not client.open():
            print(f"[FAIL] 연결 실패: {device_name}")
            return False

        print(f"[OK] 연결 성공: {device_name}")

        # DO0 켜기 (주소 8)
        print(f"\n[1] DO0 ON 명령 전송...")
        result = client.write_single_coil(8, True)
        if result:
            print(f"[OK] DO0 ON 성공")
            time.sleep(1)

            # 상태 확인
            do_bits = client.read_coils(8, 4)
            if do_bits and do_bits[0]:
                print(f"[OK] DO0 상태 확인: ON")
                print(f"   전체 DO 상태: {['ON' if b else 'OFF' for b in do_bits]}")
        else:
            print(f"[FAIL] DO0 ON 실패")

        time.sleep(2)

        # DO0 끄기
        print(f"\n[2] DO0 OFF 명령 전송...")
        result = client.write_single_coil(8, False)
        if result:
            print(f"[OK] DO0 OFF 성공")
            time.sleep(1)

            # 상태 확인
            do_bits = client.read_coils(8, 4)
            if do_bits and not do_bits[0]:
                print(f"[OK] DO0 상태 확인: OFF")
                print(f"   전체 DO 상태: {['ON' if b else 'OFF' for b in do_bits]}")
        else:
            print(f"[FAIL] DO0 OFF 실패")

        print(f"\n[OK] {device_name} 테스트 완료")
        return True

    except Exception as e:
        print(f"[ERROR] 테스트 중 오류: {e}")
        return False

    finally:
        client.close()


def main():
    """메인 함수"""
    print("\n" + "="*60)
    print("도커 외부에서 시뮬레이터 DO 제어 테스트")
    print("="*60)

    # 테스트할 장비 (도커 외부에서는 localhost 사용)
    devices = [
        {'name': 'Lane1', 'host': '127.0.0.1', 'port': 5020},
        {'name': 'Lane2', 'host': '127.0.0.1', 'port': 5021},
        {'name': 'Lane3', 'host': '127.0.0.1', 'port': 5022},
        {'name': 'Lane4', 'host': '127.0.0.1', 'port': 5023},
    ]

    print(f"\n테스트 대상: {len(devices)}대 장비")
    print("-"*60)

    results = []

    for device in devices:
        success = test_do_control(device['name'], device['host'], device['port'])
        results.append((device['name'], success))
        time.sleep(1)

    # 결과 요약
    print("\n" + "="*60)
    print("테스트 결과 요약")
    print("="*60)

    success_count = sum(1 for _, success in results if success)

    for name, success in results:
        status = "[OK] 성공" if success else "[FAIL] 실패"
        print(f"  {name:10s}: {status}")

    print("-"*60)
    print(f"  합계: {success_count}/{len(devices)}대 성공")
    print("="*60 + "\n")


if __name__ == '__main__':
    main()

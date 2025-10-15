#!/usr/bin/env python3
"""
Modbus TCP Simulator 테스트 스크립트

시뮬레이터에 연결하여 입출력 제어를 테스트합니다.
"""

import time
from pyModbusTCP.client import ModbusClient


def test_device(device_name: str, host: str, port: int):
    """
    특정 장비 테스트

    Args:
        device_name: 장비 이름
        host: IP 주소
        port: 포트 번호
    """
    print(f"\n{'='*60}")
    print(f"🧪 테스트: {device_name} ({host}:{port})")
    print(f"{'='*60}")

    # Modbus 클라이언트 생성
    client = ModbusClient(host=host, port=port, timeout=2.0)

    try:
        # 연결
        if not client.open():
            print(f"❌ 연결 실패: {device_name}")
            return False

        print(f"✅ 연결 성공: {device_name}")

        # 1. DI 읽기 (주소 0-3)
        print(f"\n📥 디지털 입력 (DI) 읽기:")
        di_bits = client.read_discrete_inputs(0, 4)
        if di_bits:
            print(f"   DI0-DI3: {di_bits}")
            for i, state in enumerate(di_bits):
                print(f"   DI{i}: {'ON' if state else 'OFF'}")
        else:
            print(f"   ❌ DI 읽기 실패")

        # 2. DO 읽기 (주소 8-11)
        print(f"\n📤 디지털 출력 (DO) 읽기:")
        do_bits = client.read_coils(8, 4)
        if do_bits:
            print(f"   DO0-DO3: {do_bits}")
            for i, state in enumerate(do_bits):
                print(f"   DO{i}: {'ON' if state else 'OFF'}")
        else:
            print(f"   ❌ DO 읽기 실패")

        # 3. DO 제어 테스트 (DO0을 ON → OFF)
        print(f"\n🔧 디지털 출력 (DO) 제어 테스트:")

        # DO0 ON
        print(f"   DO0 ON 명령...")
        result = client.write_single_coil(8, True)
        if result:
            print(f"   ✅ DO0 ON 성공")
            time.sleep(1)

            # 상태 확인
            do_bits = client.read_coils(8, 4)
            if do_bits and do_bits[0]:
                print(f"   ✅ DO0 상태 확인: ON")
        else:
            print(f"   ❌ DO0 ON 실패")

        # DO0 OFF
        print(f"   DO0 OFF 명령...")
        result = client.write_single_coil(8, False)
        if result:
            print(f"   ✅ DO0 OFF 성공")
            time.sleep(1)

            # 상태 확인
            do_bits = client.read_coils(8, 4)
            if do_bits and not do_bits[0]:
                print(f"   ✅ DO0 상태 확인: OFF")
        else:
            print(f"   ❌ DO0 OFF 실패")

        print(f"\n✅ {device_name} 테스트 완료")
        return True

    except Exception as e:
        print(f"❌ 테스트 중 오류: {e}")
        return False

    finally:
        client.close()


def main():
    """메인 함수"""
    print("\n" + "="*60)
    print("🧪 Modbus TCP Simulator 테스트")
    print("="*60)

    # 테스트할 장비 목록
    devices = [
        {'name': 'Lane1', 'host': '127.0.0.1', 'port': 5020},
        {'name': 'Lane2', 'host': '127.0.0.1', 'port': 5021},
        {'name': 'Lane3', 'host': '127.0.0.1', 'port': 5022},
        {'name': 'Lane4', 'host': '127.0.0.1', 'port': 5023},
    ]

    print(f"\n📋 테스트 대상: {len(devices)}대 장비")
    print("-"*60)

    results = []

    for device in devices:
        success = test_device(device['name'], device['host'], device['port'])
        results.append((device['name'], success))
        time.sleep(1)

    # 결과 요약
    print("\n" + "="*60)
    print("📊 테스트 결과 요약")
    print("="*60)

    success_count = sum(1 for _, success in results if success)

    for name, success in results:
        status = "✅ 성공" if success else "❌ 실패"
        print(f"  {name:10s}: {status}")

    print("-"*60)
    print(f"  합계: {success_count}/{len(devices)}대 성공")
    print("="*60 + "\n")


if __name__ == '__main__':
    main()

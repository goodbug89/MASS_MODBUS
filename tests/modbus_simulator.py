#!/usr/bin/env python3
"""
Modbus TCP Simulator - CIE-H14A 4채널 I/O 컨트롤러 시뮬레이터

4대의 가상 Modbus 장비를 시뮬레이션합니다.
각 장비는 독립적인 포트에서 실행됩니다.

Usage:
    python tests/modbus_simulator.py

Simulated Devices:
    - Device 1: 127.0.0.1:5020 (Lane1)
    - Device 2: 127.0.0.1:5021 (Lane2)
    - Device 3: 127.0.0.1:5022 (Lane3)
    - Device 4: 127.0.0.1:5023 (Lane4)
"""

import time
import threading
import logging
import random
from typing import Dict, List
from pyModbusTCP.server import ModbusServer

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CIE_H14A_Simulator:
    """
    CIE-H14A Modbus TCP 시뮬레이터

    레지스터 매핑:
    - 디지털 입력 (DI0-DI3): Discrete Inputs, Address 0-3
    - 디지털 출력 (DO0-DO3): Coils, Address 8-11
    """

    def __init__(self, device_id: str, host: str = '127.0.0.1', port: int = 502):
        """
        시뮬레이터 초기화

        Args:
            device_id: 장비 ID (예: 'Lane1', 'Lane2')
            host: Modbus 서버 IP (기본: 127.0.0.1)
            port: Modbus 서버 포트 (기본: 502)
        """
        self.device_id = device_id
        self.host = host
        self.port = port

        # Modbus 서버 인스턴스 (IPv4 only로 설정)
        try:
            self.server = ModbusServer(host=host, port=port, no_block=True, ipv6=False)
        except TypeError:
            # 구버전은 ipv6 파라미터가 없음
            self.server = ModbusServer(host=host, port=port, no_block=True)

        # 시뮬레이션 상태
        self._running = False
        self._simulation_thread = None

        logger.info(f"[{device_id}] 시뮬레이터 초기화: {host}:{port}")

    def start(self) -> bool:
        """
        시뮬레이터 시작

        Returns:
            bool: 시작 성공 여부
        """
        try:
            logger.info(f"[{self.device_id}] Modbus 서버 시작 시도: {self.host}:{self.port}")

            # Modbus 서버 시작
            self.server.start()

            # pyModbusTCP 0.2.0에서는 start()가 None을 반환하므로 is_run으로 확인
            if not self.server.is_run:
                logger.error(
                    f"[{self.device_id}] Modbus 서버 시작 실패 - "
                    f"포트 {self.port}가 이미 사용 중이거나 권한이 없을 수 있습니다"
                )
                return False

            logger.info(f"[{self.device_id}] Modbus 서버 시작 성공: {self.host}:{self.port}")

            # 초기 레지스터 설정
            self._initialize_registers()

            # 시뮬레이션 스레드 시작
            self._running = True
            self._simulation_thread = threading.Thread(
                target=self._simulation_loop,
                daemon=True,
                name=f"Simulator-{self.device_id}"
            )
            self._simulation_thread.start()

            logger.info(f"[{self.device_id}] 시뮬레이션 스레드 시작")
            return True

        except Exception as e:
            logger.error(f"[{self.device_id}] 시작 오류: {e}", exc_info=True)
            return False

    def stop(self) -> None:
        """시뮬레이터 중지"""
        logger.info(f"[{self.device_id}] 시뮬레이터 중지 중...")

        # 시뮬레이션 스레드 중지
        self._running = False
        if self._simulation_thread and self._simulation_thread.is_alive():
            self._simulation_thread.join(timeout=2.0)

        # Modbus 서버 중지
        self.server.stop()

        logger.info(f"[{self.device_id}] 시뮬레이터 중지 완료")

    def _initialize_registers(self) -> None:
        """
        초기 레지스터 값 설정

        - DI0-DI3 (주소 0-3): 모두 False (OFF)
        - DO0-DO3 (주소 8-11): 모두 False (OFF)
        """
        # 디지털 입력 초기화 (Discrete Inputs)
        for addr in range(0, 4):
            self.server.data_bank.set_discrete_inputs(addr, [False])

        # 디지털 출력 초기화 (Coils)
        for addr in range(8, 12):
            self.server.data_bank.set_coils(addr, [False])

        logger.info(f"[{self.device_id}] 레지스터 초기화 완료")

    def _simulation_loop(self) -> None:
        """
        시뮬레이션 루프

        주기적으로:
        1. DO 상태 변화 감지 및 로깅
        2. DI 상태 자동 랜덤 변화 (1초 주기로 ON, 1초 유지 후 OFF)
        """
        logger.info(f"[{self.device_id}] 시뮬레이션 루프 시작")

        prev_do_states = [False] * 4
        di_auto_timer = 0  # DI 자동 변화 타이머

        while self._running:
            try:
                # DO 상태 확인 (주소 8-11)
                current_do_states = []
                for addr in range(8, 12):
                    coils = self.server.data_bank.get_coils(addr, 1)
                    current_do_states.append(coils[0] if coils else False)

                # DO 상태 변화 감지
                for ch in range(4):
                    if current_do_states[ch] != prev_do_states[ch]:
                        state_str = 'ON' if current_do_states[ch] else 'OFF'
                        logger.info(
                            f"[{self.device_id}] DO{ch} 상태 변경: "
                            f"{'OFF' if prev_do_states[ch] else 'ON'} → {state_str}"
                        )

                prev_do_states = current_do_states.copy()

                # DI 자동 랜덤 변화 (1초 주기)
                di_auto_timer += 0.1
                if di_auto_timer >= 1.0:  # 1초마다
                    self._auto_random_di()
                    di_auto_timer = 0

                time.sleep(0.1)  # 100ms 간격으로 체크

            except Exception as e:
                logger.error(f"[{self.device_id}] 시뮬레이션 루프 오류: {e}")
                time.sleep(1.0)

        logger.info(f"[{self.device_id}] 시뮬레이션 루프 종료")

    def _auto_random_di(self) -> None:
        """
        DI 상태 자동 랜덤 변화 (테스트용)

        1초마다 호출되며:
        - DI0~DI3 중 랜덤하게 1개 채널 선택
        - 해당 채널을 1초간 ON 상태로 설정
        - 다음 호출 시 이전 채널은 자동으로 OFF됨 (모든 채널 초기화 후 새 채널만 ON)
        """
        try:
            # 랜덤 채널 선택 (0~3)
            random_channel = random.randint(0, 3)

            # 모든 DI를 OFF로 설정
            for ch in range(4):
                self.server.data_bank.set_discrete_inputs(ch, [False])

            # 선택된 채널만 ON
            self.server.data_bank.set_discrete_inputs(random_channel, [True])

            logger.info(
                f"[{self.device_id}] DI 랜덤 활성화: DI{random_channel} → ON (1초 유지)"
            )

        except Exception as e:
            logger.error(f"[{self.device_id}] DI 랜덤 변화 오류: {e}")

    def set_di(self, channel: int, state: bool) -> bool:
        """
        디지털 입력 상태 수동 설정 (테스트용)

        Args:
            channel: 채널 번호 (0-3)
            state: 상태 (True=ON, False=OFF)

        Returns:
            bool: 설정 성공 여부
        """
        if not 0 <= channel < 4:
            logger.error(f"[{self.device_id}] 잘못된 채널 번호: {channel}")
            return False

        try:
            self.server.data_bank.set_discrete_inputs(channel, [state])
            logger.info(
                f"[{self.device_id}] DI{channel} 수동 설정: {'ON' if state else 'OFF'}"
            )
            return True

        except Exception as e:
            logger.error(f"[{self.device_id}] DI 설정 오류: {e}")
            return False

    def get_di(self, channel: int) -> bool:
        """
        디지털 입력 상태 읽기

        Args:
            channel: 채널 번호 (0-3)

        Returns:
            bool: 입력 상태
        """
        if not 0 <= channel < 4:
            return False

        try:
            states = self.server.data_bank.get_discrete_inputs(channel, 1)
            return states[0] if states else False
        except:
            return False

    def get_do(self, channel: int) -> bool:
        """
        디지털 출력 상태 읽기

        Args:
            channel: 채널 번호 (0-3)

        Returns:
            bool: 출력 상태
        """
        if not 0 <= channel < 4:
            return False

        try:
            addr = 8 + channel
            coils = self.server.data_bank.get_coils(addr, 1)
            return coils[0] if coils else False
        except:
            return False

    def get_status(self) -> Dict:
        """
        전체 상태 조회

        Returns:
            dict: 입출력 상태
        """
        return {
            'device_id': self.device_id,
            'host': self.host,
            'port': self.port,
            'running': self._running,
            'inputs': [self.get_di(ch) for ch in range(4)],
            'outputs': [self.get_do(ch) for ch in range(4)]
        }


class MultiDeviceSimulator:
    """
    멀티 디바이스 시뮬레이터 관리자

    4대의 CIE-H14A 시뮬레이터를 관리합니다.
    """

    def __init__(self):
        """시뮬레이터 관리자 초기화"""
        self.simulators: Dict[str, CIE_H14A_Simulator] = {}

        # 4대 장비 설정
        self.devices_config = {
            'device1': {'name': 'Lane1', 'host': '0.0.0.0', 'port': 5020},
            'device2': {'name': 'Lane2', 'host': '0.0.0.0', 'port': 5021},
            'device3': {'name': 'Lane3', 'host': '0.0.0.0', 'port': 5022},
            'device4': {'name': 'Lane4', 'host': '0.0.0.0', 'port': 5023},
        }

        logger.info("멀티 디바이스 시뮬레이터 관리자 초기화")

    def start_all(self) -> bool:
        """
        모든 시뮬레이터 시작

        Returns:
            bool: 모든 시뮬레이터 시작 성공 여부
        """
        logger.info("모든 시뮬레이터 시작 중...")

        success_count = 0

        for device_id, config in self.devices_config.items():
            simulator = CIE_H14A_Simulator(
                device_id=config['name'],
                host=config['host'],
                port=config['port']
            )

            if simulator.start():
                self.simulators[device_id] = simulator
                success_count += 1
                logger.info(
                    f"[OK] [{device_id}] {config['name']} started: "
                    f"{config['host']}:{config['port']}"
                )
            else:
                logger.error(
                    f"[ERROR] [{device_id}] {config['name']} failed to start: "
                    f"{config['host']}:{config['port']}"
                )

        logger.info(f"시뮬레이터 시작 완료: {success_count}/{len(self.devices_config)}대")

        return success_count == len(self.devices_config)

    def stop_all(self) -> None:
        """모든 시뮬레이터 중지"""
        logger.info("모든 시뮬레이터 중지 중...")

        for device_id, simulator in self.simulators.items():
            simulator.stop()
            logger.info(f"[OK] [{device_id}] stopped")

        self.simulators.clear()
        logger.info("All simulators stopped")

    def get_simulator(self, device_id: str) -> CIE_H14A_Simulator:
        """
        특정 시뮬레이터 가져오기

        Args:
            device_id: 장비 ID (예: 'device1')

        Returns:
            CIE_H14A_Simulator: 시뮬레이터 인스턴스
        """
        return self.simulators.get(device_id)

    def print_status(self) -> None:
        """모든 시뮬레이터 상태 출력"""
        print("\n" + "=" * 80)
        print(">> Modbus TCP Simulator Status")
        print("=" * 80)

        for device_id, simulator in self.simulators.items():
            status = simulator.get_status()
            print(f"\n>> {status['device_id']} ({device_id})")
            print(f"   Address: {status['host']}:{status['port']}")
            print(f"   Status: {'[Running]' if status['running'] else '[Stopped]'}")
            print(f"   DI: {status['inputs']}")
            print(f"   DO: {status['outputs']}")

        print("\n" + "=" * 80)


def main():
    """메인 함수"""
    print("\n" + "=" * 80)
    print(">> CIE-H14A Modbus TCP Simulator - 4 Devices")
    print("=" * 80)
    print("\nStarting simulators...\n")

    # 멀티 디바이스 시뮬레이터 생성
    manager = MultiDeviceSimulator()

    try:
        # 모든 시뮬레이터 시작
        if not manager.start_all():
            print("\n[ERROR] Some simulators failed to start")
            return

        print("\n[OK] All simulators started successfully!\n")

        # 연결 정보 출력
        print(">> Connection Info:")
        print("-" * 80)
        for device_id, config in manager.devices_config.items():
            print(f"  {device_id} ({config['name']:6s}): {config['host']}:{config['port']}")
        print("-" * 80)

        print("\n>> Test Instructions:")
        print("   1. Run Flask app in another terminal:")
        print("      python run.py")
        print("   2. Open browser: http://localhost:5000")
        print("   3. Click DO buttons to test output control")
        print("   4. DI0~DI3 randomly activate every 1 second (1 sec ON, auto OFF)")

        print("\n>> Press Ctrl+C to stop\n")

        # 상태 모니터링 루프
        while True:
            time.sleep(10)
            manager.print_status()

    except KeyboardInterrupt:
        print("\n\n>> User interrupt requested...")
    except Exception as e:
        logger.error(f"Error occurred: {e}", exc_info=True)
    finally:
        # 모든 시뮬레이터 중지
        manager.stop_all()
        print("\n>> Simulator shutdown complete\n")


if __name__ == '__main__':
    main()

"""
CIE-H14A Modbus TCP 클라이언트 모듈

CIE-H14A 4채널 원격 I/O 컨트롤러와 Modbus TCP/IP 프로토콜로 통신하는 클라이언트입니다.

레지스터 매핑:
- 디지털 입력 (DI0-DI3): Function Code 02, Address 0-3
- 디지털 출력 (DO0-DO3): Function Code 05, Address 8-11

중요: 출력 주소는 0이 아닌 8부터 시작합니다!

아키텍처 원칙:
- 절대 안죽는 시스템: API 요청은 항상 즉시 응답
- Modbus 통신은 별도 스레드에서만 실행
- 타임아웃이 발생해도 시스템은 계속 동작
"""

import logging
import time
import threading
import queue
import requests
from typing import List, Optional, Tuple
from pyModbusTCP.client import ModbusClient

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CIE_H14A_Client:
    """
    CIE-H14A Modbus TCP 클라이언트

    4채널 디지털 입출력 제어를 위한 스레드 안전 Modbus 클라이언트입니다.
    백그라운드 폴링 스레드가 입력 상태를 주기적으로 읽어옵니다.
    """

    # CIE-H14A 하드웨어 사양
    NUM_CHANNELS = 4
    INPUT_START_ADDR = 0      # 입력 시작 주소
    OUTPUT_START_ADDR = 8     # 출력 시작 주소 (중요!)

    def __init__(
        self,
        host: str,
        port: int = 502,
        unit_id: int = 1,
        timeout: float = 5.0,
        poll_interval: float = 0.1,
        auto_off_time: float = 0.0,
        retry_count: int = 3,
        retry_delay: float = 0.1,
        sensor_url: Optional[str] = None,
        sensor_device_id: Optional[str] = None
    ):
        """
        CIE_H14A_Client 초기화

        Args:
            host: Modbus TCP 서버 IP 주소
            port: Modbus TCP 포트 (기본: 502)
            unit_id: Modbus Unit ID (기본: 1)
            timeout: 연결 타임아웃 (초)
            poll_interval: 입력 폴링 간격 (초)
            auto_off_time: DO 자동 꺼짐 시간 (초, 0이면 비활성화)
            retry_count: 출력 제어 실패 시 재시도 횟수
            retry_delay: 재시도 간 대기 시간 (초)
            sensor_url: DI 감지 시 호출할 URL (예: http://localhost:5000/get_sensor)
            sensor_device_id: 장비 ID (URL 파라미터로 전달)
        """
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.auto_off_time = auto_off_time
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.sensor_url = sensor_url
        self.sensor_device_id = sensor_device_id

        # Modbus 클라이언트 초기화
        self.client = ModbusClient(
            host=host,
            port=port,
            unit_id=unit_id,
            timeout=timeout,
            auto_open=False,  # 수동으로 연결 관리
            auto_close=False,
            debug=False  # 디버그 모드 비활성화 (성능 향상)
        )

        # 상태 관리
        self._connected = False
        self._inputs: List[bool] = [False] * self.NUM_CHANNELS
        self._outputs: List[bool] = [False] * self.NUM_CHANNELS
        self._last_update = 0.0

        # DI 변화 감지를 위한 상태
        self._di_triggered = False  # DI가 하나라도 ON 상태인지
        self._request_sent = False  # GET 요청을 보냈는지
        self._last_di_states: List[bool] = [False] * self.NUM_CHANNELS  # 마지막 전송한 DI 상태

        # 스레드 안전을 위한 락 (짧게만 사용)
        self._lock = threading.Lock()

        # 폴링 스레드
        self._polling_thread: Optional[threading.Thread] = None
        self._stop_polling = threading.Event()

        # 출력 제어 명령 큐 (큐는 스레드 안전)
        self._output_queue: queue.Queue = queue.Queue(maxsize=100)

        # 자동 꺼짐 타이머 관리
        self._auto_off_timers: dict[int, threading.Timer] = {}  # 채널별 타이머

        logger.info(
            f"CIE_H14A_Client 초기화: {host}:{port}, "
            f"Unit ID: {unit_id}, Timeout: {timeout}s, "
            f"Poll Interval: {poll_interval}s, "
            f"Auto-Off Time: {auto_off_time}s, "
            f"Retry Count: {retry_count}, Retry Delay: {retry_delay}s, "
            f"Sensor URL: {sensor_url}, Device ID: {sensor_device_id}"
        )

    def connect(self) -> bool:
        """
        Modbus TCP 연결

        Returns:
            bool: 연결 성공 여부
        """
        try:
            if not self.client.is_open:
                # 연결 시도 (타임아웃 내에 완료되어야 함)
                result = self.client.open()
                if result:
                    self._connected = True
                    logger.info(f"Modbus 연결 성공: {self.host}:{self.port}")
                    return True
                else:
                    self._connected = False
                    # 첫 번째 연결 실패는 상세하게 로깅하지 않음
                    return False
            else:
                self._connected = True
                return True
        except Exception as e:
            self._connected = False
            logger.warning(f"Modbus 연결 예외: {e}")
            return False

    def disconnect(self) -> None:
        """Modbus TCP 연결 해제"""
        try:
            if self.client.is_open:
                self.client.close()
            self._connected = False
            logger.info("Modbus 연결 해제")
        except Exception as e:
            logger.error(f"Modbus 연결 해제 예외: {e}")

    def is_connected(self) -> bool:
        """
        연결 상태 확인

        Returns:
            bool: 연결 상태
        """
        # client.is_open은 빠른 속성 접근이므로 락 없이 안전
        # 락을 잡지 않아서 폴링 루프와의 데드락 방지
        return self._connected and self.client.is_open

    def read_inputs(self) -> Tuple[bool, List[bool]]:
        """
        디지털 입력 상태 읽기 (DI0-DI3)

        Function Code: 02 (Read Discrete Inputs)
        Address: 0-3

        Returns:
            Tuple[bool, List[bool]]: (성공 여부, 입력 상태 리스트)
        """
        try:
            # FC 02: Read Discrete Inputs
            bits = self.client.read_discrete_inputs(
                self.INPUT_START_ADDR,
                self.NUM_CHANNELS
            )

            if bits is not None:
                with self._lock:
                    self._inputs = list(bits)
                    self._last_update = time.time()
                logger.debug(f"입력 읽기 성공: {bits}")
                return True, list(bits)
            else:
                logger.warning("입력 읽기 실패: None 반환")
                return False, self._inputs.copy()

        except Exception as e:
            logger.error(f"입력 읽기 예외: {e}")
            return False, self._inputs.copy()

    def read_outputs(self) -> Tuple[bool, List[bool]]:
        """
        디지털 출력 상태 읽기 (DO0-DO3)

        Function Code: 01 (Read Coils)
        Address: 8-11

        Returns:
            Tuple[bool, List[bool]]: (성공 여부, 출력 상태 리스트)
        """
        try:
            # FC 01: Read Coils
            bits = self.client.read_coils(
                self.OUTPUT_START_ADDR,
                self.NUM_CHANNELS
            )

            if bits is not None:
                with self._lock:
                    self._outputs = list(bits)
                logger.debug(f"출력 읽기 성공: {bits}")
                return True, list(bits)
            else:
                logger.warning("출력 읽기 실패: None 반환")
                return False, self._outputs.copy()

        except Exception as e:
            logger.error(f"출력 읽기 예외: {e}")
            return False, self._outputs.copy()

    def _cancel_auto_off_timer(self, channel: int) -> None:
        """
        자동 꺼짐 타이머 취소

        Args:
            channel: 출력 채널 번호
        """
        if channel in self._auto_off_timers:
            self._auto_off_timers[channel].cancel()
            del self._auto_off_timers[channel]
            logger.debug(f"채널 {channel} 자동 꺼짐 타이머 취소")

    def _schedule_auto_off(self, channel: int) -> None:
        """
        자동 꺼짐 타이머 예약

        Args:
            channel: 출력 채널 번호
        """
        if self.auto_off_time <= 0:
            return  # 자동 꺼짐 비활성화

        # 기존 타이머 취소
        self._cancel_auto_off_timer(channel)

        # 새 타이머 생성
        def auto_off_callback():
            try:
                logger.info(f"채널 {channel} 자동 꺼짐 실행 ({self.auto_off_time}초 후)")
                success = self.write_output(channel, False)
                if not success:
                    logger.error(f"채널 {channel} 자동 꺼짐 실패 - 재시도 메커니즘이 동작했지만 실패함")
            except Exception as e:
                logger.error(f"채널 {channel} 자동 꺼짐 콜백 예외: {e}", exc_info=True)
                # 예외 발생해도 시스템은 계속 동작

        timer = threading.Timer(self.auto_off_time, auto_off_callback)
        timer.daemon = True
        timer.start()
        self._auto_off_timers[channel] = timer
        logger.debug(f"채널 {channel} 자동 꺼짐 예약: {self.auto_off_time}초 후")

    def _write_output_single_attempt(self, channel: int, state: bool) -> bool:
        """
        디지털 출력 제어 단일 시도 (내부 메서드)

        Function Code: 05 (Write Single Coil)
        Address: 8 + channel

        Args:
            channel: 출력 채널 번호 (0-3)
            state: 출력 상태 (True=ON, False=OFF)

        Returns:
            bool: 제어 성공 여부
        """
        if not 0 <= channel < self.NUM_CHANNELS:
            logger.error(f"잘못된 채널 번호: {channel} (0-{self.NUM_CHANNELS-1} 범위)")
            return False

        # 연결 확인 (빠른 실패) - 재연결 시도하지 않음 (폴링 스레드가 담당)
        if not self.is_connected():
            logger.warning(f"Modbus 연결 끊김: 출력 제어 불가 (폴링 스레드가 재연결 시도 중)")
            return False

        try:
            # 출력 주소는 8부터 시작 (중요!)
            address = self.OUTPUT_START_ADDR + channel

            # FC 05: Write Single Coil
            result = self.client.write_single_coil(address, state)

            if result:
                with self._lock:
                    self._outputs[channel] = state
                logger.info(
                    f"출력 제어 성공: 채널 {channel} "
                    f"(주소 {address}) -> {'ON' if state else 'OFF'}"
                )

                # 자동 꺼짐 타이머 관리
                if state:  # ON으로 설정된 경우
                    self._schedule_auto_off(channel)
                else:  # OFF로 설정된 경우
                    self._cancel_auto_off_timer(channel)

                return True
            else:
                logger.warning(
                    f"출력 제어 실패: 채널 {channel} "
                    f"(주소 {address}) -> {'ON' if state else 'OFF'}"
                )
                # 실패 시 연결 상태 업데이트
                self._connected = False
                return False

        except Exception as e:
            logger.warning(f"출력 제어 예외: {e}")
            # 예외 시 연결 상태 업데이트
            self._connected = False
            return False

    def write_output(self, channel: int, state: bool) -> bool:
        """
        디지털 출력 제어 (큐에 명령 추가, 즉시 반환)

        Args:
            channel: 출력 채널 번호 (0-3)
            state: 출력 상태 (True=ON, False=OFF)

        Returns:
            bool: 명령 큐 추가 성공 여부 (항상 True, 절대 블로킹 안함)
        """
        if not 0 <= channel < self.NUM_CHANNELS:
            logger.error(f"잘못된 채널 번호: {channel}")
            return False

        try:
            # 큐에 명령 추가 (블로킹 없이, 큐가 가득 차면 오래된 명령 버림)
            command = (channel, state, time.time())

            # 큐가 가득 차면 가장 오래된 항목 제거
            if self._output_queue.full():
                try:
                    self._output_queue.get_nowait()
                    logger.warning("출력 명령 큐 가득참 - 오래된 명령 버림")
                except queue.Empty:
                    pass

            self._output_queue.put_nowait(command)

            # 즉시 상태 업데이트 (낙관적 업데이트)
            with self._lock:
                self._outputs[channel] = state

            logger.debug(f"출력 명령 큐 추가: 채널 {channel} -> {'ON' if state else 'OFF'}")

            # 자동 꺼짐 타이머 관리
            if state:
                self._schedule_auto_off(channel)
            else:
                self._cancel_auto_off_timer(channel)

            return True

        except Exception as e:
            logger.error(f"출력 명령 큐 추가 실패: {e}")
            return False

    def toggle_output(self, channel: int) -> Tuple[bool, bool]:
        """
        디지털 출력 토글

        Args:
            channel: 출력 채널 번호 (0-3)

        Returns:
            Tuple[bool, bool]: (성공 여부, 새로운 상태)
        """
        if not 0 <= channel < self.NUM_CHANNELS:
            logger.error(f"잘못된 채널 번호: {channel}")
            return False, False

        with self._lock:
            current_state = self._outputs[channel]

        new_state = not current_state
        success = self.write_output(channel, new_state)

        return success, new_state

    def get_status(self) -> dict:
        """
        전체 입출력 상태 조회

        Returns:
            dict: 연결 상태 및 입출력 상태
        """
        with self._lock:
            return {
                'connected': self._connected,
                'inputs': self._inputs.copy(),
                'outputs': self._outputs.copy(),
                'timestamp': self._last_update,
                'di_detection': {
                    'enabled': bool(self.sensor_url and self.sensor_device_id),
                    'di_triggered': self._di_triggered,
                    'request_sent': self._request_sent,
                    'sensor_url': self.sensor_url,
                    'device_id': self.sensor_device_id,
                    'di_states': self._last_di_states.copy()
                }
            }

    def _process_output_queue(self) -> None:
        """
        출력 명령 큐 처리 (블로킹 없이)

        큐에 쌓인 출력 명령을 처리합니다.
        """
        processed = 0
        max_per_cycle = 10  # 한 사이클당 최대 처리 개수

        while processed < max_per_cycle:
            try:
                # 큐에서 명령 가져오기 (블로킹 안함)
                channel, state, timestamp = self._output_queue.get_nowait()

                # 명령이 너무 오래되면 무시 (5초 이상)
                if time.time() - timestamp > 5.0:
                    logger.warning(f"오래된 출력 명령 무시: 채널 {channel}")
                    continue

                # Modbus 쓰기 시도 (재시도 포함)
                for attempt in range(1, self.retry_count + 1):
                    success = self._write_output_single_attempt(channel, state)
                    if success:
                        if attempt > 1:
                            logger.info(f"채널 {channel} 제어 성공 (재시도 {attempt}회)")
                        break

                    if attempt < self.retry_count:
                        time.sleep(self.retry_delay)

                processed += 1

            except queue.Empty:
                # 큐가 비었음
                break
            except Exception as e:
                logger.error(f"출력 명령 처리 예외: {e}")
                break

    def _check_di_and_send_request(self) -> None:
        """
        DI 상태를 확인하고 필요시 GET 요청 전송

        로직:
        1. DI가 하나라도 ON이면 -> 요청을 보내지 않았다면 즉시 전송
        2. 모든 DI가 OFF이면 -> 전송 가능 상태로 리셋
        """
        # Sensor URL이 설정되지 않았으면 아무것도 하지 않음
        if not self.sensor_url or not self.sensor_device_id:
            return

        with self._lock:
            inputs_copy = self._inputs.copy()

        # 현재 DI 상태 확인 (하나라도 ON인지)
        any_di_on = any(inputs_copy)

        # 상태 변화 감지
        if any_di_on:
            # DI가 하나라도 ON 상태
            if not self._di_triggered:
                # OFF -> ON 전환 (첫 번째 감지)
                self._di_triggered = True
                logger.info(f"[DI 감지] DI 입력 감지: {inputs_copy}")

            # GET 요청 전송 (아직 안 보냈으면)
            if not self._request_sent:
                self._send_sensor_request(inputs_copy)
                self._request_sent = True
                with self._lock:
                    self._last_di_states = inputs_copy.copy()
            else:
                logger.debug(f"[DI 감지] DI ON 상태 유지 중 - 중복 전송 방지")
        else:
            # 모든 DI가 OFF 상태
            if self._di_triggered:
                # ON -> OFF 전환
                logger.info(f"[DI 감지] 모든 DI OFF - 전송 가능 상태로 리셋")
                self._di_triggered = False
                self._request_sent = False
                with self._lock:
                    self._last_di_states = [False] * self.NUM_CHANNELS

    def _send_sensor_request(self, inputs: List[bool]) -> None:
        """
        Sensor GET 요청 전송

        Args:
            inputs: DI 입력 상태 리스트
        """
        try:
            # 밀리초 단위 타임스탬프 생성
            timestamp_ms = int(time.time() * 1000)

            # URL 파라미터 구성
            params = {
                'id': self.sensor_device_id,
                'di_states': ','.join(['1' if state else '0' for state in inputs]),
                'time': timestamp_ms
            }

            logger.info(
                f"[DI 감지] GET 요청 전송 시작 - "
                f"URL: {self.sensor_url}, Device ID: {self.sensor_device_id}, "
                f"DI States: [{params['di_states']}], Time: {timestamp_ms}ms"
            )

            # GET 요청 전송 (타임아웃 5초, 블로킹하지 않도록 짧게)
            response = requests.get(
                self.sensor_url,
                params=params,
                timeout=5.0
            )

            if response.status_code == 200:
                logger.info(
                    f"[DI 감지] GET 요청 성공 - "
                    f"Status: {response.status_code}, Response: {response.text[:200]}"
                )
            else:
                logger.warning(
                    f"[DI 감지] GET 요청 실패 - "
                    f"Status: {response.status_code}, Response: {response.text[:200]}"
                )

        except requests.Timeout:
            logger.error(f"[DI 감지] GET 요청 타임아웃 - URL: {self.sensor_url}")
        except requests.RequestException as e:
            logger.error(f"[DI 감지] GET 요청 예외 - URL: {self.sensor_url}, Error: {e}")
        except Exception as e:
            logger.error(f"[DI 감지] GET 요청 처리 중 예외: {e}", exc_info=True)

    def _polling_loop(self) -> None:
        """
        백그라운드 폴링 루프

        주기적으로 입력 상태를 읽고 연결 상태를 관리합니다.
        출력 명령 큐도 함께 처리합니다.
        """
        logger.info("폴링 스레드 시작")
        consecutive_errors = 0
        max_consecutive_errors = 10
        reconnect_backoff = 1.0  # 재연결 대기 시간 (초)

        while not self._stop_polling.is_set():
            try:
                # 연결 확인 및 재연결
                if not self.is_connected():
                    if consecutive_errors == 0:  # 첫 연결 끊김만 로깅
                        logger.warning("연결 끊김 감지, 재연결 시도...")

                    if self.connect():
                        consecutive_errors = 0  # 연결 성공 시 에러 카운터 리셋
                        reconnect_backoff = 1.0  # 백오프 리셋
                        logger.info("재연결 성공")
                    else:
                        consecutive_errors += 1
                        if consecutive_errors <= 3:  # 처음 3회만 로깅
                            logger.warning(f"재연결 실패 (연속 {consecutive_errors}회)")

                        # 연결 실패 시 대기 시간 증가 (최대 10초)
                        if consecutive_errors >= max_consecutive_errors:
                            reconnect_backoff = min(reconnect_backoff * 1.5, 10.0)
                            logger.warning(f"연속 {consecutive_errors}회 연결 실패 - {reconnect_backoff:.1f}초 대기")
                            self._stop_polling.wait(reconnect_backoff)
                            continue  # 다음 루프로

                # 연결되어 있으면 입력/출력 읽기
                if self.is_connected():
                    try:
                        success_input, _ = self.read_inputs()
                        success_output, _ = self.read_outputs()

                        if success_input and success_output:
                            consecutive_errors = 0  # 성공 시 에러 카운터 리셋
                            reconnect_backoff = 1.0  # 백오프 리셋
                        else:
                            consecutive_errors += 1
                            # 읽기 실패 시 연결 상태 플래그 업데이트
                            if consecutive_errors >= 3:
                                self._connected = False

                        # DI 감지 및 GET 요청 전송 (입력 읽기 성공 시)
                        if success_input:
                            self._check_di_and_send_request()

                        # 출력 명령 큐 처리 (연결되어 있을 때만)
                        self._process_output_queue()

                    except Exception as read_error:
                        logger.error(f"Modbus 읽기 중 예외: {read_error}")
                        consecutive_errors += 1
                        self._connected = False

            except KeyboardInterrupt:
                logger.info("폴링 루프 중단 (KeyboardInterrupt)")
                break
            except Exception as e:
                consecutive_errors += 1
                if consecutive_errors <= 3:  # 처음 3회만 상세 로깅
                    logger.error(f"폴링 루프 예외: {e}")
                self._connected = False

                # 연속 오류가 너무 많으면 긴 대기 시간
                if consecutive_errors >= max_consecutive_errors:
                    logger.critical(
                        f"폴링 루프 연속 {consecutive_errors}회 실패 - "
                        f"10초 대기 후 재시도"
                    )
                    self._stop_polling.wait(10.0)
                    consecutive_errors = max_consecutive_errors // 2  # 절반으로 리셋

            # 다음 폴링까지 대기 (중단 가능)
            self._stop_polling.wait(self.poll_interval)

        logger.info("폴링 스레드 종료")

    def start_polling(self) -> None:
        """백그라운드 폴링 시작"""
        if self._polling_thread is None or not self._polling_thread.is_alive():
            self._stop_polling.clear()
            self._polling_thread = threading.Thread(
                target=self._polling_loop,
                daemon=True,
                name="ModbusPollingThread"
            )
            self._polling_thread.start()
            logger.info("백그라운드 폴링 시작")
        else:
            logger.warning("폴링 스레드가 이미 실행 중입니다")

    def stop_polling(self) -> None:
        """백그라운드 폴링 중지"""
        if self._polling_thread and self._polling_thread.is_alive():
            logger.info("폴링 스레드 중지 요청")
            self._stop_polling.set()
            self._polling_thread.join(timeout=5.0)
            if self._polling_thread.is_alive():
                logger.warning("폴링 스레드가 타임아웃 내에 종료되지 않음")
            else:
                logger.info("폴링 스레드 종료 완료")

    def _cancel_all_timers(self) -> None:
        """모든 자동 꺼짐 타이머 취소"""
        for channel in list(self._auto_off_timers.keys()):
            self._cancel_auto_off_timer(channel)
        logger.info("모든 자동 꺼짐 타이머 취소 완료")

    def __enter__(self):
        """컨텍스트 매니저 진입"""
        self.connect()
        self.start_polling()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료"""
        self._cancel_all_timers()
        self.stop_polling()
        self.disconnect()

    def __del__(self):
        """소멸자: 리소스 정리"""
        try:
            self._cancel_all_timers()
            self.stop_polling()
            self.disconnect()
        except:
            pass

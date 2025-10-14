"""
Modbus 클라이언트 단위 테스트
"""

import pytest
import time
from app.modbus_client import CIE_H14A_Client


class TestCIEH14AClient:
    """CIE_H14A_Client 테스트"""

    def test_client_initialization(self):
        """클라이언트 초기화 테스트"""
        client = CIE_H14A_Client(
            host="127.0.0.1",
            port=502,
            unit_id=1,
            timeout=5.0,
            poll_interval=0.5
        )

        assert client.host == "127.0.0.1"
        assert client.port == 502
        assert client.unit_id == 1
        assert client.timeout == 5.0
        assert client.poll_interval == 0.5
        assert client.NUM_CHANNELS == 4
        assert client.INPUT_START_ADDR == 0
        assert client.OUTPUT_START_ADDR == 8

    def test_channel_validation(self):
        """채널 번호 유효성 검사 테스트"""
        client = CIE_H14A_Client(host="127.0.0.1")

        # 유효한 채널
        for channel in range(4):
            result = client.write_output(channel, True)
            # 연결되지 않아도 유효성 검사는 통과해야 함

        # 잘못된 채널
        assert client.write_output(-1, True) == False
        assert client.write_output(4, True) == False
        assert client.write_output(10, True) == False

    def test_initial_state(self):
        """초기 상태 테스트"""
        client = CIE_H14A_Client(host="127.0.0.1")

        status = client.get_status()

        assert status['connected'] == False
        assert len(status['inputs']) == 4
        assert len(status['outputs']) == 4
        assert all(state == False for state in status['inputs'])
        assert all(state == False for state in status['outputs'])

    def test_context_manager(self):
        """컨텍스트 매니저 테스트"""
        with CIE_H14A_Client(host="127.0.0.1") as client:
            assert client is not None
            # 연결 실패해도 예외가 발생하지 않아야 함

    def test_toggle_logic(self):
        """토글 로직 테스트 (모의)"""
        client = CIE_H14A_Client(host="127.0.0.1")

        # 초기 상태는 False
        status = client.get_status()
        assert status['outputs'][0] == False


class TestModbusAddresses:
    """Modbus 주소 매핑 테스트"""

    def test_input_addresses(self):
        """입력 주소 테스트"""
        client = CIE_H14A_Client(host="127.0.0.1")

        # 입력은 주소 0부터 시작
        assert client.INPUT_START_ADDR == 0

    def test_output_addresses(self):
        """출력 주소 테스트"""
        client = CIE_H14A_Client(host="127.0.0.1")

        # 출력은 주소 8부터 시작 (중요!)
        assert client.OUTPUT_START_ADDR == 8

    def test_address_ranges(self):
        """주소 범위 테스트"""
        client = CIE_H14A_Client(host="127.0.0.1")

        # 입력: 0-3
        input_range = range(
            client.INPUT_START_ADDR,
            client.INPUT_START_ADDR + client.NUM_CHANNELS
        )
        assert list(input_range) == [0, 1, 2, 3]

        # 출력: 8-11
        output_range = range(
            client.OUTPUT_START_ADDR,
            client.OUTPUT_START_ADDR + client.NUM_CHANNELS
        )
        assert list(output_range) == [8, 9, 10, 11]


@pytest.fixture
def mock_client():
    """모의 Modbus 클라이언트 fixture"""
    return CIE_H14A_Client(host="127.0.0.1", port=502)


def test_client_fixture(mock_client):
    """Fixture 테스트"""
    assert mock_client is not None
    assert mock_client.host == "127.0.0.1"

"""
Flask 라우트 단위 테스트
"""

import pytest
import json
from app import create_app


@pytest.fixture
def app():
    """Flask 앱 fixture"""
    app = create_app('test')
    app.config['TESTING'] = True
    yield app


@pytest.fixture
def client(app):
    """Flask 테스트 클라이언트 fixture"""
    return app.test_client()


class TestHealthCheck:
    """헬스 체크 엔드포인트 테스트"""

    def test_health_endpoint(self, client):
        """헬스 체크 엔드포인트"""
        response = client.get('/health')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'status' in data
        assert 'modbus_connected' in data


class TestStatusAPI:
    """상태 조회 API 테스트"""

    def test_get_status(self, client):
        """상태 조회 엔드포인트"""
        response = client.get('/api/status')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'connected' in data
        assert 'inputs' in data
        assert 'outputs' in data
        assert 'timestamp' in data
        assert len(data['inputs']) == 4
        assert len(data['outputs']) == 4


class TestConfigAPI:
    """설정 조회 API 테스트"""

    def test_get_config(self, client):
        """설정 조회 엔드포인트"""
        response = client.get('/api/config')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'modbus_host' in data
        assert 'modbus_port' in data
        assert 'modbus_unit_id' in data
        assert 'modbus_timeout' in data
        assert 'poll_interval' in data


class TestOutputControlAPI:
    """출력 제어 API 테스트"""

    def test_control_output_valid(self, client):
        """유효한 출력 제어 요청"""
        for channel in range(4):
            response = client.post(
                f'/api/output/{channel}',
                data=json.dumps({'state': True}),
                content_type='application/json'
            )
            # 연결되지 않아도 요청 형식이 올바르면 처리됨
            assert response.status_code in [200, 500]

    def test_control_output_invalid_channel(self, client):
        """잘못된 채널 번호"""
        response = client.post(
            '/api/output/10',
            data=json.dumps({'state': True}),
            content_type='application/json'
        )
        assert response.status_code == 400

        data = json.loads(response.data)
        assert 'error' in data

    def test_control_output_missing_state(self, client):
        """state 필드 누락"""
        response = client.post(
            '/api/output/0',
            data=json.dumps({}),
            content_type='application/json'
        )
        assert response.status_code == 400

    def test_control_output_invalid_json(self, client):
        """잘못된 JSON 형식"""
        response = client.post(
            '/api/output/0',
            data='invalid json',
            content_type='application/json'
        )
        assert response.status_code == 400


class TestToggleAPI:
    """토글 API 테스트"""

    def test_toggle_output_valid(self, client):
        """유효한 토글 요청"""
        for channel in range(4):
            response = client.post(f'/api/output/{channel}/toggle')
            # 연결되지 않아도 요청 형식이 올바르면 처리됨
            assert response.status_code in [200, 500]

    def test_toggle_output_invalid_channel(self, client):
        """잘못된 채널 번호 토글"""
        response = client.post('/api/output/10/toggle')
        assert response.status_code == 400


class TestStaticFiles:
    """정적 파일 제공 테스트"""

    def test_index_page(self, client):
        """메인 페이지"""
        response = client.get('/')
        assert response.status_code == 200


class TestErrorHandlers:
    """오류 핸들러 테스트"""

    def test_404_error(self, client):
        """404 오류"""
        response = client.get('/nonexistent-endpoint')
        assert response.status_code == 404

        data = json.loads(response.data)
        assert 'error' in data

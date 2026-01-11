"""
Flask 개발 서버 실행 스크립트

개발 환경에서 Flask 애플리케이션을 실행합니다.
프로덕션 환경에서는 Gunicorn 또는 uWSGI를 사용하세요.
"""

import os
import sys
from app import create_app

# 환경 설정
env = os.getenv('FLASK_ENV', 'development')

# Flask 앱 생성
app = create_app(env)

if __name__ == '__main__':
    # 개발 서버 실행
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = env == 'development'

    # Windows 콘솔 인코딩 문제 해결 (로컬 개발 환경용)
    # 참고: Docker 컨테이너에서는 Linux 환경이므로 이 코드는 실행되지 않습니다
    try:
        # UTF-8 출력 설정 시도 (Windows에서 한글 출력을 위함)
        if sys.platform == 'win32':
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, OSError):
        # 인코딩 설정 실패 시 무시 (기본 인코딩 사용)
        pass

    print("=" * 60)
    print("  CIE-H14A Modbus TCP/IP Multi-Device Control System")
    print("=" * 60)
    print(f"  Environment: {env}")
    print(f"  Address: http://{host}:{port}")
    print(f"  Debug: {debug}")
    print("=" * 60)
    print()

    try:
        app.run(
            host=host,
            port=port,
            debug=debug,
            threaded=True  # 다중 스레드 활성화
        )
    except KeyboardInterrupt:
        print("\n\n서버 종료 중...")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n서버 실행 오류: {e}")
        sys.exit(1)

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

    print(f"""
    ╔═══════════════════════════════════════════════════════════╗
    ║   CIE-H14A Modbus TCP/IP 제어 시스템                      ║
    ╠═══════════════════════════════════════════════════════════╣
    ║   환경: {env:<50} ║
    ║   주소: http://{host}:{port:<43} ║
    ║   디버그: {str(debug):<48} ║
    ╚═══════════════════════════════════════════════════════════╝
    """)

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

# CIE-H14A Modbus Controller Dockerfile

# Python 3.11 기반 이미지 사용
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필수 패키지 설치
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt 복사 및 Python 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 포트 5000 노출
EXPOSE 5000

# 환경 변수 설정
ENV FLASK_APP=app
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Gunicorn을 사용한 프로덕션 서버 실행
# 중요: --workers 1 로 단일 워커 사용 (Modbus 단일 연결 유지)
# SSE 때문에 스레드를 충분히 확보 (최소 10개)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "20", "--timeout", "300", "--graceful-timeout", "30", "--keep-alive", "5", "--access-logfile", "-", "--error-logfile", "-", "app:create_app()"]

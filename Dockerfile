FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    TZ=Asia/Seoul \
    DOCKER_CONTAINER=1

WORKDIR /app

# 타임존 설정 (KST)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# 전체 프로젝트 복사
COPY . /app

EXPOSE 8000

CMD ["python", "hub_server.py"]

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_PROFILE=api \
    API_HOST=0.0.0.0 \
    API_PORT=8000 \
    HEALTH_HOST=0.0.0.0 \
    TELEGRAM_HEALTH_PORT=8088 \
    EVOLUTION_HEALTH_PORT=8087

WORKDIR /app

COPY requirements.lock.txt ./
RUN python -m pip install --upgrade pip \
    && pip install -r requirements.lock.txt

COPY . .

EXPOSE 8000 8087 8088

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python docker/healthcheck.py

CMD ["python", "docker/run_profile.py"]

# Image unique : serveur web, worker Celery et ordonnanceur.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential libpq-dev libjpeg-dev zlib1g-dev curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
ARG DEV=0
RUN if [ "$DEV" = "1" ]; then pip install -r requirements-dev.txt; else pip install -r requirements.txt; fi

COPY . .

RUN adduser --system --group --no-create-home dpfc \
 && mkdir -p /app/logs /app/media /app/staticfiles \
 && chown -R dpfc:dpfc /app
USER dpfc

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", \
     "--workers", "3", "--timeout", "120", "--access-logfile", "-"]

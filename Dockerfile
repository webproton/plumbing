# syntax=docker/dockerfile:1

# ---------- build: собираем wheels ----------
FROM python:3.12-slim-bookworm AS builder
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# ---------- runtime ----------
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/code \
    DJANGO_SETTINGS_MODULE=config.settings

RUN useradd --create-home --uid 1000 app
WORKDIR /code

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

COPY --chown=app:app . /code
RUN mkdir -p /code/staticfiles /code/media /code/private_media \
    && chown -R app:app /code/staticfiles /code/media /code/private_media

USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "-c", "gunicorn.conf.py"]

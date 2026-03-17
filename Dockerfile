# Dockerfile (Django, PostgreSQL 14+, SCRAM)
FROM python:3.10-bookworm
# FROM python:3.10-slim-bullseye
# python:3.10-bookworm
# python:3.10-slim-bookworm
# python:3.10-slim-bullseye

# Создаем рабочую директорию
WORKDIR /code

# Устанавливаем Python-зависимости
COPY ./requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y psycopg2-binary \
    && pip install --no-cache-dir psycopg2

# Копируем проект
COPY . /code

# Делаем config и manage.py читаемыми для всех
# RUN chmod -R a+rX /code/config /code/manage.py
RUN chmod -R a+rX /code/config /code/app/manage.py

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libjpeg-dev \
    zlib1g-dev \
    libpq-dev \
    postgresql-client \
    postgresql-server-dev-all \
    postgis \
    gdal-bin \
    gettext \
    && rm -rf /var/lib/apt/lists/*


# Экспонируем порт для Gunicorn
EXPOSE 8000

# Настраиваем переменные окружения
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/code

# Запускаем Gunicorn
CMD ["gunicorn", "config.wsgi:application", "--chdir", "/code", "--bind", "0.0.0.0:8000", "--log-level", "debug"]

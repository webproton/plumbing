"""Конфигурация gunicorn (значения переопределяются переменными окружения)."""

import multiprocessing
import os

bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")
workers = int(os.getenv("GUNICORN_WORKERS", min(multiprocessing.cpu_count() * 2 + 1, 5)))
threads = int(os.getenv("GUNICORN_THREADS", 2))
timeout = int(os.getenv("GUNICORN_TIMEOUT", 60))
graceful_timeout = 30
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
forwarded_allow_ips = "*"  # заголовки X-Forwarded-* ставит только наш nginx (сеть compose)

"""Celery: фоновые задачи. Воркер: celery -A config worker; расписание: celery -A config beat."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("plumbing")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

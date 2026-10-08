import os

# Тестовое окружение: не зависит от локального .env для критичных параметров.
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ["CACHE_URL"] = "locmemcache://"
os.environ["EMAIL_BACKEND"] = "django.core.mail.backends.locmem.EmailBackend"
os.environ.setdefault("ACCOUNT_EMAIL_VERIFICATION", "mandatory")

import pytest


@pytest.fixture(autouse=True)
def _clear_cache():
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app.apps.accounts"
    label = "accounts"

    def ready(self):
        import app.apps.accounts.signals  # noqa: F401 — регистрирует обработчики сигналов

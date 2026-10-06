from django.apps import AppConfig


class WarehouseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app.apps.warehouse'

    def ready(self):
        # Import signals inside ready() so they register on startup
        import app.apps.warehouse.signals
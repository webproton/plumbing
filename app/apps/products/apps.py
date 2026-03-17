from django.apps import AppConfig


class ProductsConfig(AppConfig):
    name = 'app.apps.products'


    def ready(self):
        import app.apps.products.signals 
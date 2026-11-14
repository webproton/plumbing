from django.apps import AppConfig


class ProductsConfig(AppConfig):
    name = "app.apps.products"
    verbose_name = "Каталог"

    def ready(self):
        from .search import register_lookups

        register_lookups()  # field__compact: поиск слитно/раздельно («twbkt» = «TWB KT»)

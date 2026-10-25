from django.core.management.base import BaseCommand, CommandError

from app.apps.products.catalog.services import ensure_taxonomy
from app.apps.products.catalog.taxonomy import VERTICALS


class Command(BaseCommand):
    help = "Создать дерево категорий направления: plumbing | tools | bikes | furniture | all"

    def add_arguments(self, parser):
        parser.add_argument("vertical", choices=[*VERTICALS, "all"])

    def handle(self, *args, **options):
        keys = list(VERTICALS) if options["vertical"] == "all" else [options["vertical"]]
        for key in keys:
            if key not in VERTICALS:
                raise CommandError(f"Нет направления {key}")
            leaves = ensure_taxonomy(VERTICALS[key])
            self.stdout.write(self.style.SUCCESS(f"{VERTICALS[key].name}: категорий {len(leaves)}"))

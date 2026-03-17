from django.core.management.base import BaseCommand
from django.utils.text import slugify
from transliterate import translit
from app.apps.products.models import Product, ProductVariant  # Замените 'app.apps.products' на путь к вашим моделям

class Command(BaseCommand):
    help = 'Fix slugs for Product and ProductVariant objects with non-ASCII characters'

    def handle(self, *args, **kwargs):
        # Исправление slug для Product
        products = Product.objects.filter(slug__isnull=False)
        for product in products:
            if product.name:
                translit_name = translit(product.name, 'ru', reversed=True)
                base_slug = slugify(translit_name)
                slug = base_slug
                counter = 1
                while Product.objects.filter(slug=slug).exclude(pk=product.pk).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                if product.slug != slug:
                    self.stdout.write(f"Updating Product slug for {product.name}: {product.slug} -> {slug}")
                    Product.objects.filter(pk=product.pk).update(slug=slug)
                else:
                    self.stdout.write(f"Product slug for {product.name} is already correct: {slug}")

        # Исправление slug для ProductVariant
        variants = ProductVariant.objects.filter(slug__isnull=False)
        for variant in variants:
            text_to_slug = f"{variant.product.name}-{variant.variant_name}" if variant.variant_name else variant.product.name
            translit_text = translit(text_to_slug, 'ru', reversed=True)
            base_slug = slugify(translit_text)
            slug = base_slug
            counter = 1
            while ProductVariant.objects.filter(slug=slug).exclude(pk=variant.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            if variant.slug != slug:
                self.stdout.write(f"Updating ProductVariant slug for {variant.product.name} - {variant.variant_name}: {variant.slug} -> {slug}")
                ProductVariant.objects.filter(pk=variant.pk).update(slug=slug)
            else:
                self.stdout.write(f"ProductVariant slug for {variant.product.name} - {variant.variant_name} is already correct: {slug}")
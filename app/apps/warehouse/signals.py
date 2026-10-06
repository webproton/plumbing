from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import StockMovement
from .services import recalculate_variant_stock

@receiver(post_save, sender=StockMovement)
@receiver(post_delete, sender=StockMovement)
def update_stock_cache_on_movement(sender, instance, **kwargs):
    """
    Сигнал срабатывает автоматически при ЛЮБОМ сохранении или 
    удалении движения на складе и обновляет кэш у товара.
    """
    if instance.variant:
        recalculate_variant_stock(instance.variant)
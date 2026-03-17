# В сигнале user_logged_in
from django.contrib.auth.signals import user_logged_in
from .models import   Product
from django.dispatch import receiver
from django.db.models.signals import post_save
from .utils.banner_generator import generate_banner




# @receiver(post_save, sender=Product)
# def generate_banner_on_save(sender, instance, **kwargs):
#     generate_banner(instance)

from django.conf import settings

# В сигнале user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


# автоматически создаём профиль при создании пользователя
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance, email=instance.email, password="")


# автоматически сохраняем профиль при сохранении пользователя
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, "profile"):
        profile = instance.profile
        profile.email = instance.email
        profile.save()

import os
import secrets

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from app.apps.accounts.models import User  # ⚡️ поправь путь под своё приложение


class Command(BaseCommand):
    help = "Создаёт 5 менеджеров с email и telegram chat_id из env"

    def handle(self, *args, **kwargs):
        emails = [
            "im_manager_1@example.com",
            "im_manager_2@example.com",
            "im_manager_3@example.com",
            "im_manager_4@example.com",
            "im_manager_5@example.com",
        ]

        # достаём переменную MANAGERS прямо из окружения
        TELEGRAM_MANAGERS = [m.strip() for m in os.getenv("MANAGERS", "").split(",") if m.strip()]

        managers_group, _ = Group.objects.get_or_create(name="Managers")

        for i, email in enumerate(emails, start=1):
            telegram_id = TELEGRAM_MANAGERS[i - 1] if i - 1 < len(TELEGRAM_MANAGERS) else None

            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": f"Менеджер {i}",
                    "is_active": True,
                    "is_admin": True,
                    "telegram": telegram_id,
                },
            )
            if created:
                # случайный пароль показывается один раз; потом его можно сменить через «Забыли пароль»
                password = secrets.token_urlsafe(12)
                user.set_password(password)
                user.save()
                user.groups.add(managers_group)
                self.stdout.write(self.style.SUCCESS(f"✅ Создан {email}, пароль: {password}, telegram={telegram_id}"))
            else:
                if telegram_id and user.telegram != telegram_id:
                    user.telegram = telegram_id
                    user.save(update_fields=["telegram"])
                    self.stdout.write(self.style.WARNING(f"♻ Обновлён {email}, telegram={telegram_id}"))
                else:
                    self.stdout.write(self.style.WARNING(f"⚠ {email} уже существует без изменений"))

        self.stdout.write(self.style.SUCCESS("🎉 Все менеджеры созданы/обновлены"))

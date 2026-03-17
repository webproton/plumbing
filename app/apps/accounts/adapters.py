# accounts/adapters.py
from allauth.account.adapter import DefaultAccountAdapter
from django.core.mail import send_mail
from django.conf import settings

class CustomAccountAdapter(DefaultAccountAdapter):
    def get_email_confirmation_url(self, request, emailconfirmation):
        # Формируем ссылку на фронтенд для подтверждения
        base_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
        return f"{base_url}/confirm-email/{emailconfirmation.key}/"
    
    def send_confirmation_mail(self, request, emailconfirmation, signup):
        activate_url = f"{settings.FRONTEND_URL}/confirm-email/{emailconfirmation.key}/"
        subject = "Подтверждение регистрации"
        message = (
            f"Здравствуйте!\n\n"
            f"Вы получили это письмо, потому что адрес {emailconfirmation.email_address.email} "
            f"был использован для регистрации на {request.get_host()}.\n\n"
            f"Для подтверждения перейдите по ссылке:\n{activate_url}\n\n"
            f"Спасибо, что выбрали наш сервис!"
        )
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [emailconfirmation.email_address.email])

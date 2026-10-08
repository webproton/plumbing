from django.conf import settings


class RealIPMiddleware:
    """
    За nginx REMOTE_ADDR — это адрес прокси, из-за чего throttling, axes и
    django-ratelimit считали всех пользователей одним клиентом.
    Если TRUSTED_PROXY=True, берём реальный IP из X-Real-IP, который выставляет наш nginx.
    Заголовок от клиента напрямую не принимается: включайте флаг только за своим прокси.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = getattr(settings, "TRUSTED_PROXY", False)

    def __call__(self, request):
        if self.enabled:
            real_ip = request.META.get("HTTP_X_REAL_IP", "").strip()
            if real_ip:
                request.META["REMOTE_ADDR"] = real_ip
        return self.get_response(request)

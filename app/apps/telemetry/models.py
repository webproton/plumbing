from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


class DailyTelemetryMetrics(models.Model):
    date = models.DateField(db_index=True)
    page_views = models.IntegerField(default=0)
    clicks = models.IntegerField(default=0)
    logins = models.IntegerField(default=0)
    unique_users = models.IntegerField(default=0)

class TelemetryEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name="ID события")

    # Пользователь (может быть null для анонимов)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="telemetry_events",
        null=True,
        blank=True,
        verbose_name="Пользователь"
    )
    page_url = models.URLField(null=True, blank=True, verbose_name="URL страницы")
    referrer = models.URLField(null=True, blank=True, verbose_name="Referrer")
    duration_ms = models.IntegerField(null=True, blank=True, verbose_name="Длительность события (мс)")

    # Уникальные идентификаторы клиента
    device_id = models.CharField(max_length=128, db_index=True, verbose_name="Device ID (постоянный)")
    session_id = models.CharField(max_length=128, db_index=True, verbose_name="Session ID (временный)")

    # Клиент (браузер/OS/устройство)
    browser = models.CharField(max_length=100, null=True, blank=True, verbose_name="Браузер")
    browser_version = models.CharField(max_length=50, null=True, blank=True, verbose_name="Версия браузера")
    os = models.CharField(max_length=100, null=True, blank=True, verbose_name="ОС")
    os_version = models.CharField(max_length=50, null=True, blank=True, verbose_name="Версия ОС")
    device_type = models.CharField(max_length=50, null=True, blank=True, verbose_name="Тип устройства (desktop/mobile/tablet)")
    device_model = models.CharField(max_length=100, null=True, blank=True, verbose_name="Модель устройства")
    device_vendor = models.CharField(
    max_length=100, 
    null=True, 
    blank=True, 
    verbose_name="Производитель устройства"
    )
    # Экран
    screen_width = models.IntegerField(null=True, blank=True, verbose_name="Ширина экрана")
    screen_height = models.IntegerField(null=True, blank=True, verbose_name="Высота экрана")
    device_pixel_ratio = models.FloatField(null=True, blank=True, verbose_name="Device Pixel Ratio")
    color_depth = models.IntegerField(null=True, blank=True, verbose_name="Глубина цвета")

    # Сеть
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True, verbose_name="Реальный IP клиента")
    ip_chain = models.TextField(null=True, blank=True, verbose_name="Цепочка IP (VPN / прокси / балансировщики)")
    timezone = models.CharField(max_length=100, null=True, blank=True, verbose_name="Таймзона клиента")
    lang = models.CharField(max_length=50, null=True, blank=True, verbose_name="Язык браузера")
    connection_type = models.CharField(max_length=50, null=True, blank=True, verbose_name="Тип подключения (wifi/cellular)")
    connection_rtt = models.IntegerField(null=True, blank=True, verbose_name="RTT сети (ms)")
    connection_downlink = models.FloatField(null=True, blank=True, verbose_name="Скорость downlink (Mbps)")
    # Geo 

    country = models.CharField(max_length=50, null=True, blank=True, verbose_name="Страна (ISO 3166-1 alpha-2)")
    city = models.CharField(max_length=100, null=True, blank=True, verbose_name="Город")

    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    # Hardware info
    cpu_cores = models.IntegerField(null=True, blank=True, verbose_name="Количество CPU ядер")
    ram_gb = models.FloatField(null=True, blank=True, verbose_name="RAM в ГБ")
    touch_support = models.BooleanField(default=False, verbose_name="Есть поддержка touch")

    # Fingerprints
    webgl_vendor = models.CharField(max_length=200, null=True, blank=True, db_index=True, verbose_name="WebGL vendor")
    webgl_renderer = models.CharField(max_length=200, null=True, blank=True, verbose_name="WebGL renderer")
    canvas_hash = models.CharField(max_length=200, null=True, blank=True, db_index=True, verbose_name="Canvas fingerprint hash")
    audio_hash = models.CharField(max_length=200, null=True, blank=True, db_index=True, verbose_name="Audio fingerprint hash")
    user_segment = models.CharField(max_length=50, null=True, blank=True, verbose_name="Сегмент пользователя")
    timestamp_client = models.DateTimeField(null=True, blank=True, verbose_name="Время события на клиенте")
    # Техническое
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Время события")

    event_type = models.CharField(
    max_length=100,
    choices=[
        ('page_view', 'Page View'),
        ('click', 'Click'),
        ('purchase', 'Purchase'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('error', 'Error'),
    ],
    default='page_view',
    verbose_name="Тип события")
    
    event_data = models.JSONField(null=True, blank=True, verbose_name="Данные события")

    def __str__(self):
        user_str = f"user={self.user.username}" if self.user else "anon"
        return f"{user_str} | {self.device_id} | {self.browser} on {self.os}"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['device_id', 'created_at']),
            models.Index(fields=['ip_address', 'canvas_hash', 'webgl_vendor', 'audio_hash']),
            models.Index(fields=['session_id', 'created_at']),
        ]
        verbose_name = "Событие телеметрии"
        verbose_name_plural = "События телеметрии"
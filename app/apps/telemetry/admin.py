from django.contrib import admin
from .models import TelemetryEvent
from django.db.models import Count
# Register your models here.
from django.contrib.sessions.models import Session
from django.utils import timezone
from django.http import JsonResponse
from django.utils.dateparse import parse_date
from django.db.models.functions import TruncDate
import json

EVENT_TYPE_COLORS = {
    "login": "rgba(75, 192, 192, 0.7)",
    "logout": "rgba(255, 99, 132, 0.7)",
    "bad_user_agent": "rgba(255, 159, 64, 0.7)",
    "purchase": "rgba(153, 102, 255, 0.7)",
    # Добавь остальные типы здесь
}

# colors = [EVENT_TYPE_COLORS.get(e['event_type'], 'rgba(54, 162, 235, 0.5)') for e in event_counts]
# event_counts = list(qs.values("event_type")
#                     .annotate(count=Count("id"))
#                     .order_by("-count"))  # Сначала самые популярные события

class TelemetryEventAdmin(admin.ModelAdmin):
    # change_list_template = "admin/telemetry/telemetryevent/telemetry_event_changelist.html"
    change_list_template = "admin/telemetry/telemetryevent/change_list.html"

    list_display = ["id", "user", "ip_address", "device_id", "session_id", "os", "device_type", "city", "country", "created_at", "event_type"]
    list_filter = ["event_type", "os", "device_type", "country", "city", "created_at"]
    search_fields = ["device_id", "ip_address", "session_id", "user__email"]
    date_hierarchy = "created_at"

    def changelist_view(self, request, extra_context=None):
        qs = self.get_queryset(request)

        # Фильтр по дате
        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")
        if start_date:
            qs = qs.filter(created_at__gte=parse_date(start_date))
        if end_date:
            qs = qs.filter(created_at__lte=parse_date(end_date))

        # События по типу
        event_counts = list(qs.values("event_type").annotate(count=Count("id")).order_by("-count"))
        for e in event_counts:
            e["color"] = EVENT_TYPE_COLORS.get(e["event_type"], "rgba(54, 162, 235, 0.5)")

        # События по устройствам/странам
        device_country_counts = qs.values("device_type", "country") \
                                 .annotate(count=Count("id")) \
                                 .order_by("device_type", "country")
        device_country_counts = [
            {"label": f"{e['device_type']} / {e['country']}", "count": e["count"]}
            for e in device_country_counts
        ]

        # Динамика по дням
        timeline = list(
            qs.annotate(date=TruncDate("created_at"))
              .values("date")
              .annotate(count=Count("id"))
              .order_by("date")
        )
        timeline = [{"date": str(e["date"]), "count": e["count"]} for e in timeline]

        # Последние события
        latest_events = qs.order_by("-created_at")[:10]

        # Топ-10 пользователей
        top_users = list(
            qs.values("user__email")
              .annotate(count=Count("id"))
              .order_by("-count")[:10]
        )
        # Обрабатываем None (анонимные пользователи)
        for u in top_users:
            u["user__email"] = u["user__email"] or "Аноним"

        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({
                "event_counts": event_counts,
                "device_country_counts": device_country_counts,
                "timeline": timeline,
                 "top_users": top_users
            })

        extra_context = extra_context or {}
        extra_context.update({
            "event_counts": event_counts,
            "device_country_counts": device_country_counts,
            "timeline": timeline,
            "latest_events": latest_events,
             "top_users": top_users
        })

        return super().changelist_view(request, extra_context=extra_context)


admin.site.register(TelemetryEvent,TelemetryEventAdmin)


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ("session_key", "user", "expire_date", "is_expired")

    def user(self, obj):
        data = obj.get_decoded()
        uid = data.get("_auth_user_id")
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if uid:
            try:
                return User.objects.get(pk=uid)
            except User.DoesNotExist:
                return "—"
        return "Аноним"

    def is_expired(self, obj):
        return obj.expire_date < timezone.now()
    is_expired.boolean = True
    is_expired.short_description = "Просрочена?"
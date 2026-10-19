from django.urls import path

from .views import CitiesView, EstimateView, WarehousesView

app_name = "delivery"

urlpatterns = [
    path("np/cities/", CitiesView.as_view(), name="np-cities"),
    path("np/warehouses/", WarehousesView.as_view(), name="np-warehouses"),
    path("np/estimate/", EstimateView.as_view(), name="np-estimate"),
]

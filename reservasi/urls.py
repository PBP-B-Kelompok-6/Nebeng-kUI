from django.urls import path

from reservasi.views import show_reservasi

app_name = "reservasi"

urlpatterns = [
    path("reservasi/", show_reservasi, name="show_reservasi"),
]
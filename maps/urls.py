"""peta/urls.py  (di project urls.py: path("peta/", include("peta.urls")))"""
from django.urls import path

from . import views

app_name = "maps"

urlpatterns = [
    path("", views.halaman_peta, name="halaman"),
    path("api/titik/", views.api_titik, name="api_titik"),
    path("api/titik/<int:pk>/star/", views.api_toggle_star, name="api_toggle_star"),
    path("api/catatan/", views.api_catatan, name="api_catatan"),
    path("api/catatan/<int:pk>/", views.api_catatan_detail, name="api_catatan_detail"),
]

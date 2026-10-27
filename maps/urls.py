"""peta/urls.py  (di project urls.py: path("peta/", include("peta.urls")))"""
from django.urls import path

from . import views

app_name = "maps"

urlpatterns = [
    path("", views.halaman_peta, name="halaman"),
    path("api/titik/", views.api_titik, name="api_titik"),
]

"""maps/api_urls.py

Di portofolio/urls.py (project) tambahkan:
    path("api/v1/maps/", include("maps.api_urls")),
"""
from django.urls import path

from maps import api_views

app_name = "maps_api"

urlpatterns = [
    path("titik/", api_views.titik_list, name="titik-list"),
    path("titik/<int:pk>/", api_views.titik_detail, name="titik-detail"),
    path("titik/<int:pk>/star/", api_views.titik_star, name="titik-star"),
    path("catatan/", api_views.catatan_list, name="catatan-list"),
    path("catatan/<int:pk>/", api_views.catatan_detail, name="catatan-detail"),
]

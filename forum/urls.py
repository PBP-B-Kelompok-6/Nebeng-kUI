from django.urls import path
from . import views

app_name = "forum"

urlpatterns = [
    path("", views.FeedView.as_view(), name="feed"),
    path("buat/", views.PostCreateView.as_view(), name="create"),
    path("<int:pk>/", views.PostDetailView.as_view(), name="detail"),
    path("<int:pk>/hapus/", views.PostDeleteView.as_view(), name="delete"),
]
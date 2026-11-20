from django.urls import path

from users import api_views

app_name = "api"

urlpatterns = [
    path("auth/register/", api_views.register, name="register"),
    path("auth/login/", api_views.login_user, name="login"),
    path("auth/logout/", api_views.logout_user, name="logout"),

    path("profile/", api_views.profile_detail, name="profile"),

    path("vehicles/", api_views.vehicle_list, name="vehicle-list"),
    path("vehicles/<int:vehicle_id>/", api_views.vehicle_detail, name="vehicle-detail"),
]
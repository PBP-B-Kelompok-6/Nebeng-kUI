from django.urls import path

from users.views import login_user, logout_user, register_user, profile_view, vehicle_create, vehicle_update, vehicle_delete, profile_edit

app_name = "users"

urlpatterns = [
    path("register/", register_user, name="register"),
    path("login/", login_user, name="login"),
    path("logout/", logout_user, name="logout"),
    path("profile/", profile_view, name="profile"),

    path("profile/edit/", profile_edit, name="profile_edit"),
    path("vehicles/add/", vehicle_create, name="vehicle_add"),
    path("vehicles/<int:pk>/edit/", vehicle_update, name="vehicle_edit"),
    path("vehicles/<int:pk>/delete/", vehicle_delete, name="vehicle_delete"),
]
from django.urls import path

from users.views import (
    login_user, logout_user, register_user,
    profile_view, profile_edit,
    vehicle_create, vehicle_update, vehicle_delete,
    vehicles_json, vehicle_create_ajax, vehicle_update_ajax, vehicle_delete_ajax,
    redeem_view, redeem_ajax,
)

app_name = "users"

urlpatterns = [
    path("register/", register_user, name="register"),
    path("login/", login_user, name="login"),
    path("logout/", logout_user, name="logout"),
    path("profile/", profile_view, name="profile"),
    path("profile/edit/", profile_edit, name="profile_edit"),

    # Kendaraan: halaman HTML (cadangan tanpa JavaScript)
    path("vehicles/add/", vehicle_create, name="vehicle_add"),
    path("vehicles/<int:pk>/edit/", vehicle_update, name="vehicle_edit"),
    path("vehicles/<int:pk>/delete/", vehicle_delete, name="vehicle_delete"),

    # Kendaraan: JSON/AJAX
    path("vehicles/json/", vehicles_json, name="vehicles_json"),
    path("vehicles/add-ajax/", vehicle_create_ajax, name="vehicle_add_ajax"),
    path("vehicles/<int:pk>/edit-ajax/", vehicle_update_ajax, name="vehicle_edit_ajax"),
    path("vehicles/<int:pk>/delete-ajax/", vehicle_delete_ajax, name="vehicle_delete_ajax"),

    # Penukaran poin
    path("rewards/redeem/", redeem_view, name="redeem"),
    path("rewards/redeem-ajax/", redeem_ajax, name="redeem_ajax"),
]
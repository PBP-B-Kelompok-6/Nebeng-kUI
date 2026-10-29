import datetime
from .models import Vehicle
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render, get_object_or_404
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from django.contrib.auth.decorators import login_required

from users.forms import RegisterForm, ProfileForm, VehicleForm
from users.rewards import (
    POINTS_PER_EXCHANGE, RUPIAH_PER_EXCHANGE, exchange_points, format_rupiah,
)
from django.core.exceptions import ValidationError
from django.db.models import Count



def register_user(request):
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Akun berhasil dibuat. Silakan login.")
        return redirect("users:login")
    return render(request, "users/register.html", {"form": form})


def login_user(request):
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())

        next_url = request.POST.get("next", "")
        if not url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            next_url = settings.LOGIN_REDIRECT_URL

        response = redirect(next_url)
        response.set_cookie(
            "last_login",
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        return response
    return render(request, "users/login.html", {
        "form": form,
        "next": request.GET.get("next", ""),
    })


@require_POST
def logout_user(request):
    logout(request)
    response = redirect(settings.LOGOUT_REDIRECT_URL)
    response.delete_cookie("last_login")
    return response

# @login_required
# def profile_view(request):
#     vehicles = request.user.vehicles.all()
#     return render(request, "users/profile.html", {"vehicles": vehicles})

@login_required
def profile_edit(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profil berhasil diperbarui.")
        return redirect("users:profile")
    return render(request, "users/form_page.html", {
        "form": form,
        "title": "Edit Profil",
        "subtitle": "Perbarui data dirimu, termasuk fakultas.",
        "submit_label": "Simpan",
    })


@login_required
def vehicle_create(request):
    form = VehicleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        vehicle = form.save(commit=False)
        vehicle.owner = request.user
        vehicle.save()
        messages.success(request, "Kendaraan berhasil ditambahkan.")
        return redirect("users:profile")
    return render(request, "users/form_page.html", {
        "form": form,
        "title": "Tambah Kendaraan",
        "subtitle": "Daftarkan kendaraanmu untuk mulai memberi tebengan.",
        "submit_label": "Tambah",
    })


@login_required
def vehicle_update(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk, owner=request.user)
    form = VehicleForm(request.POST or None, instance=vehicle)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Kendaraan berhasil diperbarui.")
        return redirect("users:profile")
    return render(request, "users/form_page.html", {
        "form": form,
        "title": "Edit Kendaraan",
        "subtitle": vehicle.name,
        "submit_label": "Simpan",
    })


@login_required
@require_POST
def vehicle_delete(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk, owner=request.user)
    vehicle.delete()
    messages.success(request, "Kendaraan berhasil dihapus.")
    return redirect("users:profile")

@login_required
def profile_view(request):
    user = request.user
    all_vehicles = user.vehicles.all()

    # Filter jenis kendaraan; nilai di luar daftar diabaikan
    vehicle_filter = request.GET.get("vehicle_type", "")
    if vehicle_filter not in Vehicle.VehicleType.values:
        vehicle_filter = ""
    vehicles = (
        all_vehicles.filter(vehicle_type=vehicle_filter)
        if vehicle_filter else all_vehicles
    )

    counts = dict(
        all_vehicles.order_by().values_list("vehicle_type").annotate(n=Count("pk"))
    )
    vehicle_total = sum(counts.values())
    vehicle_tabs = [("", "Semua", vehicle_total)] + [
        (value, label, counts.get(value, 0))
        for value, label in Vehicle.VehicleType.choices
    ]
    vehicle_context = {
        "vehicles": vehicles,
        "vehicle_filter": vehicle_filter,
        "vehicle_tabs": vehicle_tabs,
        "vehicle_total": vehicle_total,
    }

    # Permintaan dari fetch: kirim potongan daftar kendaraan saja
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(request, "users/_vehicle_list.html", vehicle_context)

    remainder = user.reward_points % POINTS_PER_EXCHANGE
    return render(request, "users/profile.html", {
        **vehicle_context,
        "ride_count": user.reward_logs.count(),
        "exchange_lots": user.reward_points // POINTS_PER_EXCHANGE,
        "points_to_next": POINTS_PER_EXCHANGE - remainder,
        "progress_pct": remainder * 100 // POINTS_PER_EXCHANGE,
        "points_per_exchange": POINTS_PER_EXCHANGE,
        "rupiah_per_exchange": RUPIAH_PER_EXCHANGE,
        "recent_exchanges": user.redemptions.all()[:3],
    })


@login_required
@require_POST
def redeem_view(request):
    try:
        lots = int(request.POST.get("lots", ""))
    except ValueError:
        messages.error(request, "Masukkan jumlah paket yang valid.")
        return redirect("users:profile")

    try:
        redemption = exchange_points(request.user, lots)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        messages.success(
            request,
            f"{redemption.points} poin ditukar menjadi "
            f"{format_rupiah(redemption.amount_rupiah)}. "
            f"Saldo kamu sekarang {format_rupiah(request.user.balance)}.",
        )
    return redirect("users:profile")
import datetime
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.defaultfilters import date as date_filter
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from users.forms import ProfileForm, RegisterForm, VehicleForm
from users.models import Vehicle
from users.rewards import (
    POINTS_PER_EXCHANGE, RUPIAH_PER_EXCHANGE, eco_state, exchange_points,
    format_rupiah,
)


# --------------------------------------------------------------------------
# Autentikasi
# --------------------------------------------------------------------------
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


# --------------------------------------------------------------------------
# Helper bersama
# --------------------------------------------------------------------------
def ajax_login_required(view):
    """Seperti login_required, tapi membalas JSON 401 (bukan redirect ke
    halaman login) supaya fetch di browser bisa menanganinya."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"message": "Sesi berakhir. Silakan login lagi."}, status=401
            )
        return view(request, *args, **kwargs)
    return wrapper


def vehicle_state(user, raw_filter):
    """Kendaraan milik `user` + filter jenis + jumlah per jenis.

    Query selalu dimulai dari user.vehicles, jadi kendaraan orang lain
    tidak mungkin ikut, apa pun isi parameternya.
    """
    all_vehicles = user.vehicles.all()
    vehicle_filter = raw_filter if raw_filter in Vehicle.VehicleType.values else ""
    vehicles = (
        all_vehicles.filter(vehicle_type=vehicle_filter)
        if vehicle_filter else all_vehicles
    )
    counts = dict(
        all_vehicles.order_by().values_list("vehicle_type").annotate(n=Count("pk"))
    )
    total = sum(counts.values())
    tabs = [("", "Semua", total)] + [
        (value, label, counts.get(value, 0))
        for value, label in Vehicle.VehicleType.choices
    ]
    return vehicle_filter, vehicles, tabs, total


def vehicle_to_json(vehicle):
    return {
        "pk": vehicle.pk,
        "fields": {
            "vehicle_type": vehicle.vehicle_type,
            "vehicle_type_display": vehicle.get_vehicle_type_display(),
            "name": vehicle.name,
            "plate_number": vehicle.plate_number,
            "capacity": vehicle.capacity,
        },
    }


# --------------------------------------------------------------------------
# Profil (halaman HTML)
# --------------------------------------------------------------------------
@login_required
def profile_view(request):
    user = request.user
    vehicle_filter, vehicles, tabs, total = vehicle_state(
        user, request.GET.get("vehicle_type", "")
    )
    vehicle_context = {
        "vehicles": vehicles,
        "vehicle_filter": vehicle_filter,
        "vehicle_tabs": tabs,
        "vehicle_total": total,
    }

    # Cadangan: potongan HTML daftar kendaraan. Halaman sekarang memakai
    # endpoint JSON (vehicles_json), jadi cabang ini boleh dihapus.
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(request, "users/_vehicle_list.html", vehicle_context)

    return render(request, "users/profile.html", {
        **vehicle_context,
        **eco_state(user),
        "vehicle_form": VehicleForm(),
        "ride_count": user.reward_logs.count(),
        "points_per_exchange": POINTS_PER_EXCHANGE,
        "rupiah_per_exchange": RUPIAH_PER_EXCHANGE,
        "recent_exchanges": user.redemptions.all()[:3],
    })


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


# --------------------------------------------------------------------------
# Kendaraan: halaman HTML (tetap ada sebagai cadangan kalau JavaScript mati)
# --------------------------------------------------------------------------
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


# --------------------------------------------------------------------------
# Kendaraan: endpoint JSON/AJAX
# --------------------------------------------------------------------------
@ajax_login_required
def vehicles_json(request):
    vehicle_filter, vehicles, tabs, _total = vehicle_state(
        request.user, request.GET.get("vehicle_type", "")
    )
    return JsonResponse({
        "vehicles": [vehicle_to_json(v) for v in vehicles],
        "filter": vehicle_filter,
        "counts": {(value or "all"): count for value, _label, count in tabs},
    })


@ajax_login_required
@require_POST
def vehicle_create_ajax(request):
    form = VehicleForm(request.POST)
    if form.is_valid():
        vehicle = form.save(commit=False)
        vehicle.owner = request.user          # pemilik selalu user yang login
        vehicle.save()
        return JsonResponse(
            {"message": "Kendaraan berhasil ditambahkan.", "pk": vehicle.pk},
            status=201,
        )
    return JsonResponse({"errors": form.errors.get_json_data()}, status=400)


@ajax_login_required
@require_POST
def vehicle_update_ajax(request, pk):
    vehicle = Vehicle.objects.filter(pk=pk, owner=request.user).first()
    if vehicle is None:
        return JsonResponse({"message": "Kendaraan tidak ditemukan."}, status=404)

    form = VehicleForm(request.POST, instance=vehicle)
    if form.is_valid():
        form.save()
        return JsonResponse(
            {"message": "Kendaraan berhasil diperbarui.", "pk": vehicle.pk}
        )
    return JsonResponse({"errors": form.errors.get_json_data()}, status=400)


@ajax_login_required
@require_POST
def vehicle_delete_ajax(request, pk):
    vehicle = Vehicle.objects.filter(pk=pk, owner=request.user).first()
    if vehicle is None:
        return JsonResponse({"message": "Kendaraan tidak ditemukan."}, status=404)
    vehicle.delete()
    return JsonResponse({"message": "Kendaraan berhasil dihapus."})


# --------------------------------------------------------------------------
# Penukaran poin
# --------------------------------------------------------------------------
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


@ajax_login_required
@require_POST
def redeem_ajax(request):
    try:
        lots = int(request.POST.get("lots", ""))
    except ValueError:
        return JsonResponse(
            {"message": "Masukkan jumlah paket yang valid."}, status=400
        )

    try:
        redemption = exchange_points(request.user, lots)
    except ValidationError as exc:
        return JsonResponse({"message": exc.messages[0]}, status=400)

    user = request.user
    return JsonResponse({
        "message": (
            f"{redemption.points} poin ditukar menjadi "
            f"{format_rupiah(redemption.amount_rupiah)}. "
            f"Saldo kamu sekarang {format_rupiah(user.balance)}."
        ),
        "state": eco_state(user),
        "redemption": {
            "points": redemption.points,
            "amount_display": format_rupiah(redemption.amount_rupiah),
            "created_display": date_filter(
                timezone.localtime(redemption.created_at), "d M Y, H:i"
            ),
        },
    }, status=201)
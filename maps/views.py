"""peta/views.py"""
import json

from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.contrib.auth.decorators import login_required

from .models import *
from .overpass import ambil_titik_ui, tambah_jarak

MAKS_PANJANG = 300

@require_GET
def halaman_peta(request):
    return render(request, "maps/map.html")


@require_GET
def api_titik(request):
    qs = TitikKumpul.objects.filter(aktif=True)
 
    kategori = request.GET.get("kategori")
    if kategori:
        qs = qs.filter(kategori__in=kategori.split(","))
 
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(nama__icontains=q)
 
    titik = [t.as_dict() for t in qs]
 
    # tandai titik yang di-star oleh pengguna yang sedang login
    if request.user.is_authenticated:
        starred_ids = set(request.user.starred_titik.values_list("pk", flat=True))
    else:
        starred_ids = set()
    for t in titik:
        t["starred"] = t["pk"] in starred_ids
 
    try:
        lat = float(request.GET["lat"])
        lon = float(request.GET["lon"])
        titik = tambah_jarak(titik, lat, lon)
    except (KeyError, ValueError):
        pass  # tanpa lokasi pengguna, jarak tidak dihitung
 
    return JsonResponse({"jumlah": len(titik), "hasil": titik})

@login_required
@require_POST
def api_toggle_star(request, pk):
    titik = get_object_or_404(TitikKumpul, pk=pk, aktif=True)
    if titik.starred_by.filter(pk=request.user.pk).exists():
        titik.starred_by.remove(request.user)
        starred = False
    else:
        titik.starred_by.add(request.user)
        starred = True
    return JsonResponse({"starred": starred, "jumlah": titik.starred_by.count()})


def _baca_json(request):
    try:
        return json.loads(request.body or "{}")
    except ValueError:
        return {}
 
 
def _validasi_teks(data):
    teks = str(data.get("teks", "")).strip()
    if not teks:
        return None, "Catatan tidak boleh kosong."
    if len(teks) > MAKS_PANJANG:
        return None, f"Catatan maksimal {MAKS_PANJANG} karakter."
    return teks, None
 
 
@require_http_methods(["GET", "POST"])
def api_catatan(request):
    """GET  /maps/api/catatan/  -> daftar catatan milik user
       POST /maps/api/catatan/  -> buat catatan baru {teks, titik (pk, opsional)}"""
    if not request.user.is_authenticated:
        if request.method == "GET":
            return JsonResponse({"hasil": [], "login": False})
        return JsonResponse({"error": "Login diperlukan."}, status=401)
 
    if request.method == "GET":
        qs = request.user.catatan_penjemputan.select_related("titik")
        return JsonResponse({"hasil": [c.as_dict() for c in qs], "login": True})
 
    data = _baca_json(request)
    teks, error = _validasi_teks(data)
    if error:
        return JsonResponse({"error": error}, status=400)
 
    titik = None
    if data.get("titik"):
        titik = TitikKumpul.objects.filter(pk=data["titik"], aktif=True).first()
 
    catatan = CatatanPenjemputan.objects.create(user=request.user, teks=teks, titik=titik)
    return JsonResponse({"catatan": catatan.as_dict()}, status=201)
 
 
@require_http_methods(["PUT", "DELETE"])
def api_catatan_detail(request, pk):
    """PUT    /maps/api/catatan/<pk>/ -> ubah teks {teks}
       DELETE /maps/api/catatan/<pk>/ -> hapus"""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Login diperlukan."}, status=401)
 
    catatan = get_object_or_404(CatatanPenjemputan, pk=pk, user=request.user)
 
    if request.method == "DELETE":
        catatan.delete()
        return JsonResponse({"terhapus": True})
 
    teks, error = _validasi_teks(_baca_json(request))
    if error:
        return JsonResponse({"error": error}, status=400)
    catatan.teks = teks
    catatan.save()
    return JsonResponse({"catatan": catatan.as_dict()})
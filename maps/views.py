"""peta/views.py"""
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .overpass import ambil_titik_ui, tambah_jarak


@require_GET
def halaman_peta(request):
    return render(request, "maps/map.html")


@require_GET
def api_titik(request):
    """GET /peta/api/titik/?kategori=halte,gerbang&lat=-6.36&lon=106.83&q=fakultas"""
    titik = ambil_titik_ui(paksa_refresh=request.GET.get("refresh") == "1")

    kategori = request.GET.get("kategori")
    if kategori:
        pilihan = set(kategori.split(","))
        titik = [t for t in titik if t["kategori"] in pilihan]

    q = request.GET.get("q", "").strip().lower()
    if q:
        titik = [t for t in titik if q in t["nama"].lower()]

    try:
        lat = float(request.GET["lat"])
        lon = float(request.GET["lon"])
        titik = tambah_jarak(titik, lat, lon)
    except (KeyError, ValueError):
        pass  # tanpa lokasi pengguna, jarak tidak dihitung

    return JsonResponse({"jumlah": len(titik), "hasil": titik})

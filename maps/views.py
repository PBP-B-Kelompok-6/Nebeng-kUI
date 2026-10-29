"""peta/views.py"""
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.decorators import login_required

from .models import TitikKumpul
from .overpass import ambil_titik_ui, tambah_jarak


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
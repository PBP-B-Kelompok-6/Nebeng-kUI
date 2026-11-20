"""maps/api_views.py  (Django REST Framework)"""
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from maps.models import CatatanPenjemputan, TitikKumpul
from maps.permissions import IsSuperuserOrReadOnly
from maps.serializers import CatatanSerializer, TitikKumpulSerializer


def _baca_lokasi(request):
    """Ambil ?lat=&lon= dari query. Mengembalikan (lat, lon) atau None bila tidak valid."""
    try:
        return (
            float(request.query_params["lat"]),
            float(request.query_params["lon"]),
        )
    except (KeyError, ValueError):
        return None


# ===================================================================== TITIK
@api_view(["GET", "HEAD", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsSuperuserOrReadOnly])
def titik_list(request):
    """GET  /api/v1/maps/titik/?kategori=halte,stasiun&q=ui&lat=..&lon=..
       POST /api/v1/maps/titik/   (superuser)"""
    if request.method in ("GET", "HEAD"):
        titik = TitikKumpul.objects.filter(aktif=True).prefetch_related("starred_by")

        kategori = request.query_params.get("kategori")
        if kategori:
            titik = titik.filter(kategori__in=kategori.split(","))

        q = request.query_params.get("q", "").strip()
        if q:
            titik = titik.filter(nama__icontains=q)

        lokasi = _baca_lokasi(request)
        serializer = TitikKumpulSerializer(
            titik, many=True, context={"request": request, "lokasi": lokasi},
        )
        data = serializer.data
        if lokasi:
            data = sorted(data, key=lambda t: t["jarak_m"])   # terdekat lebih dulu
        return Response(data)

    serializer = TitikKumpulSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET", "HEAD", "PUT", "PATCH", "DELETE"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsSuperuserOrReadOnly])
def titik_detail(request, pk):
    """GET/PUT/PATCH/DELETE /api/v1/maps/titik/<pk>/"""
    queryset = TitikKumpul.objects.prefetch_related("starred_by")
    if not request.user.is_superuser:
        queryset = queryset.filter(aktif=True)   # titik nonaktif disembunyikan dari publik
    titik = get_object_or_404(queryset, pk=pk)

    if request.method in ("GET", "HEAD"):
        return Response(TitikKumpulSerializer(titik, context={"request": request}).data)

    if request.method == "DELETE":
        titik.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = TitikKumpulSerializer(
        titik, data=request.data, partial=request.method == "PATCH",
        context={"request": request},
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def titik_star(request, pk):
    """POST /api/v1/maps/titik/<pk>/star/  -> beri/batalkan star (toggle)"""
    titik = get_object_or_404(TitikKumpul, pk=pk, aktif=True)
    if titik.starred_by.filter(pk=request.user.pk).exists():
        titik.starred_by.remove(request.user)
    else:
        titik.starred_by.add(request.user)
    return Response(TitikKumpulSerializer(titik, context={"request": request}).data)


# ===================================================================== CATATAN
@api_view(["GET", "HEAD", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def catatan_list(request):
    """GET  /api/v1/maps/catatan/   -> catatan milik user yang login
       POST /api/v1/maps/catatan/   -> buat catatan {teks, titik (opsional)}"""
    if request.method in ("GET", "HEAD"):
        catatan = request.user.catatan_penjemputan.select_related("titik")
        return Response(CatatanSerializer(catatan, many=True).data)

    serializer = CatatanSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save(user=request.user)   # pemilik selalu dari session, bukan dari input
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET", "HEAD", "PUT", "PATCH", "DELETE"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def catatan_detail(request, pk):
    """GET/PUT/PATCH/DELETE /api/v1/maps/catatan/<pk>/  (hanya milik sendiri)"""
    # filter user=request.user: catatan orang lain otomatis 404
    catatan = get_object_or_404(
        CatatanPenjemputan.objects.select_related("titik"), pk=pk, user=request.user,
    )

    if request.method in ("GET", "HEAD"):
        return Response(CatatanSerializer(catatan).data)

    if request.method == "DELETE":
        catatan.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = CatatanSerializer(
        catatan, data=request.data, partial=request.method == "PATCH",
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)

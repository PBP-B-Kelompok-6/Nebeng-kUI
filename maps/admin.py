from django.contrib import admin
from .models import TitikKumpul, CatatanPenjemputan


@admin.register(TitikKumpul)
class TitikKumpulAdmin(admin.ModelAdmin):
    list_display = ("nama", "kategori", "lat", "lon", "sumber", "aktif")
    list_filter = ("kategori", "aktif", "sumber")
    search_fields = ("nama", "osm_id")


@admin.register(CatatanPenjemputan)
class CatatanPenjemputanAdmin(admin.ModelAdmin):
    list_display = ("user", "titik", "teks", "dibuat")
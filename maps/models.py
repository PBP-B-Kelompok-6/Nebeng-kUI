from django.db import models
from django.conf import settings

class TitikKumpul(models.Model):
    class Kategori(models.TextChoices):
        HALTE = "halte", "Halte Bikun"
        STASIUN = "stasiun", "Stasiun KRL"
        GERBANG = "gerbang", "Gerbang"
        FAKULTAS = "fakultas", "Fakultas"
        PERPUSTAKAAN = "perpustakaan", "Perpustakaan"
        KOS = "kos", "Area Kos"
        EV = "ev", "Stasiun EV"
        SEPEDA = "sepeda", "Sepeda Kampus"

    # id unik: "node/123" dari OSM, atau "manual/<slug>" untuk data isian tim
    osm_id = models.CharField(max_length=80, unique=True)
    nama = models.CharField(max_length=200)
    kategori = models.CharField(max_length=20, choices=Kategori.choices)
    lat = models.FloatField()
    lon = models.FloatField()
    deskripsi = models.TextField(blank=True)
    sumber = models.CharField(max_length=20, default="manual")  # "overpass" / "manual"
    aktif = models.BooleanField(default=True)
    starred_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="starred_titik", blank=True
    )

    class Meta:
        ordering = ["kategori", "nama"]
        verbose_name_plural = "Titik kumpul"

    def __str__(self):
        return f"{self.nama} ({self.get_kategori_display()})"

    def as_dict(self):
        """Format yang sama dengan hasil overpass.py, supaya JavaScript tidak perlu diubah."""
        return {
            "pk": self.pk,
            "id": self.osm_id,
            "nama": self.nama,
            "kategori": self.kategori,
            "label": self.get_kategori_display(),
            "lat": self.lat,
            "lon": self.lon,
            "deskripsi": self.deskripsi,
        }
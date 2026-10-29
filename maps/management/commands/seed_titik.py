"""
Jalankan:
    python manage.py seed_titik                       (ambil dari Overpass)
    python manage.py seed_titik --file export.json    (ambil dari file hasil export overpass-turbo)
    python manage.py seed_titik --tanpa-overpass      (hanya dari titik_manual.json, jika ada)
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from maps.models import TitikKumpul
from maps.overpass import _normalisasi, ambil_titik_ui

FILE_MANUAL = Path(__file__).resolve().parents[2] / "data" / "titik_manual.json"
TARGET_MINIMAL = 50


class Command(BaseCommand):
    help = "Isi data awal titik kumpul (Overpass, file export, atau file manual)."

    def add_arguments(self, parser):
        parser.add_argument("--tanpa-overpass", action="store_true")
        parser.add_argument("--file", help="Path JSON hasil export overpass-turbo (raw OSM data)")

    def handle(self, *args, **opts):
        baru = diperbarui = 0

        # 1) sumber utama: file export, Overpass, atau lewati
        if opts["file"]:
            path = Path(opts["file"])
            if not path.exists():
                raise CommandError(f"File tidak ditemukan: {path}")
            elemen = json.loads(path.read_text(encoding="utf-8")).get("elements", [])
            daftar, terlihat = [], set()
            for el in elemen:
                item = _normalisasi(el)
                if item and (item["nama"], item["kategori"]) not in terlihat:
                    terlihat.add((item["nama"], item["kategori"]))
                    daftar.append(item)
            self.stdout.write(f"Membaca {len(daftar)} titik dari {path.name}")
        elif not opts["tanpa_overpass"]:
            self.stdout.write("Mengambil data dari Overpass...")
            daftar = ambil_titik_ui(paksa_refresh=True)
        else:
            daftar = []

        for t in daftar:
            _, dibuat = TitikKumpul.objects.update_or_create(
                osm_id=t["id"],
                defaults={
                    "nama": t["nama"], "kategori": t["kategori"],
                    "lat": t["lat"], "lon": t["lon"],
                    "deskripsi": t["deskripsi"], "sumber": "overpass",
                },
            )
            baru += dibuat
            diperbarui += not dibuat

        # 2) file manual (opsional)
        if FILE_MANUAL.exists():
            for t in json.loads(FILE_MANUAL.read_text(encoding="utf-8")):
                _, dibuat = TitikKumpul.objects.update_or_create(
                    osm_id=f'manual/{slugify(t["nama"])}',
                    defaults={
                        "nama": t["nama"], "kategori": t["kategori"],
                        "lat": t["lat"], "lon": t["lon"],
                        "deskripsi": t.get("deskripsi", ""), "sumber": "manual",
                    },
                )
                baru += dibuat
                diperbarui += not dibuat

        total = TitikKumpul.objects.count()
        self.stdout.write(self.style.SUCCESS(f"Selesai: {baru} baru, {diperbarui} diperbarui, total {total}."))
        for kode, label in TitikKumpul.Kategori.choices:
            self.stdout.write(f"  {label}: {TitikKumpul.objects.filter(kategori=kode).count()}")
        if total == 0:
            self.stdout.write(self.style.WARNING("Belum ada data. Coba opsi --file dengan export dari overpass-turbo."))
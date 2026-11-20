"""maps/serializers.py"""
import uuid

from django.utils.html import strip_tags
from django.utils.text import slugify
from rest_framework import serializers

from maps.models import CatatanPenjemputan, TitikKumpul
from maps.overpass import haversine_km


class TitikKumpulSerializer(serializers.ModelSerializer):
    label = serializers.CharField(source="get_kategori_display", read_only=True)
    star_count = serializers.SerializerMethodField()
    is_starred = serializers.SerializerMethodField()
    jarak_m = serializers.SerializerMethodField()

    class Meta:
        model = TitikKumpul
        fields = [
            "id", "osm_id", "nama", "kategori", "label", "lat", "lon",
            "deskripsi", "aktif", "sumber",
            "star_count", "is_starred", "jarak_m",
        ]
        read_only_fields = ["id", "osm_id", "sumber"]

    # ---------- validasi ----------
    def validate_nama(self, value):
        value = strip_tags(value).strip()
        if not value:
            raise serializers.ValidationError("Nama tidak boleh kosong.")
        return value

    def validate_deskripsi(self, value):
        return strip_tags(value)

    def validate_lat(self, value):
        if not -90 <= value <= 90:
            raise serializers.ValidationError("Latitude harus antara -90 dan 90.")
        return value

    def validate_lon(self, value):
        if not -180 <= value <= 180:
            raise serializers.ValidationError("Longitude harus antara -180 dan 180.")
        return value

    def create(self, validated_data):
        # titik buatan manual tidak punya id OSM, jadi dibuatkan id unik
        slug = slugify(validated_data["nama"])[:50]
        validated_data["osm_id"] = f"manual/{slug}-{uuid.uuid4().hex[:6]}"
        validated_data["sumber"] = "manual"
        return super().create(validated_data)

    # ---------- field hasil perhitungan ----------
    def get_star_count(self, obj):
        # len(.all()) memanfaatkan prefetch_related, .count() akan query lagi
        return len(obj.starred_by.all())

    def get_is_starred(self, obj):
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return False
        return request.user in obj.starred_by.all()

    def get_jarak_m(self, obj):
        lokasi = self.context.get("lokasi")  # (lat, lon) atau None
        if not lokasi:
            return None
        return round(haversine_km(lokasi[0], lokasi[1], obj.lat, obj.lon) * 1000)


class CatatanSerializer(serializers.ModelSerializer):
    titik = serializers.PrimaryKeyRelatedField(
        queryset=TitikKumpul.objects.filter(aktif=True),
        required=False, allow_null=True,
    )
    titik_nama = serializers.SerializerMethodField()

    class Meta:
        model = CatatanPenjemputan
        fields = ["id", "teks", "titik", "titik_nama", "dibuat"]
        read_only_fields = ["id", "dibuat"]   # user diisi dari request.user, bukan dari input

    def validate_teks(self, value):
        value = strip_tags(value).strip()
        if not value:
            raise serializers.ValidationError("Catatan tidak boleh kosong.")
        return value

    def get_titik_nama(self, obj):
        return obj.titik.nama if obj.titik else ""

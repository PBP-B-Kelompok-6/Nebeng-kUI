"""peta/overpass.py
Service untuk mengambil titik strategis di kampus UI Depok dari Overpass API.
"""
import math

import requests
from django.core.cache import cache

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
CACHE_KEY = "peta_titik_ui_v1"
CACHE_TTL = 60 * 60 * 6  # 6 jam, supaya tidak membebani Overpass

# bbox kampus UI Depok: (selatan, barat, utara, timur)
BBOX = (-6.3760, 106.8120, -6.3480, 106.8400)

QUERY = """
[out:json][timeout:25];
(
  nwr["highway"="bus_stop"]({s},{w},{n},{e});
  nwr["amenity"="bus_station"]({s},{w},{n},{e});
  nwr["railway"~"^(station|halt)$"]({s},{w},{n},{e});
  nwr["barrier"="gate"]["name"]({s},{w},{n},{e});
  nwr["entrance"]["name"]({s},{w},{n},{e});
  nwr["amenity"="library"]({s},{w},{n},{e});
  nwr["amenity"="charging_station"]({s},{w},{n},{e});
  nwr["amenity"="bicycle_rental"]({s},{w},{n},{e});
  nwr["amenity"="university"]["name"]({s},{w},{n},{e});
  nwr["amenity"="college"]["name"]({s},{w},{n},{e});
  nwr["building"="university"]["name"]({s},{w},{n},{e});
);
out center tags;
"""

# kategori -> label yang tampil di badge kartu
LABEL = {
    "halte": "Halte Kampus",
    "gerbang": "Gerbang Utama",
    "perpustakaan": "Perpustakaan",
    "stasiun": "Transport Publik",
    "fakultas": "Fakultas",
    "ev": "Stasiun EV",
    "sepeda": "Sepeda Kampus",
}


def klasifikasi(tags):
    """Tentukan kategori sebuah elemen OSM dari tag-nya."""
    nama = (tags.get("name") or "").lower()
    if tags.get("railway") in ("station", "halt"):
        return "stasiun"
    if "gerbang" in nama or tags.get("barrier") == "gate" or "entrance" in tags:
        return "gerbang"
    if tags.get("highway") == "bus_stop" or tags.get("amenity") == "bus_station":
        return "halte"
    if tags.get("amenity") == "library":
        return "perpustakaan"
    if tags.get("amenity") == "charging_station":
        return "ev"
    if tags.get("amenity") == "bicycle_rental":
        return "sepeda"
    if nama.startswith("fakultas") or tags.get("amenity") in ("university", "college") \
            or tags.get("building") == "university":
        return "fakultas"
    return None


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _normalisasi(el):
    tags = el.get("tags", {})
    kategori = klasifikasi(tags)
    if not kategori:
        return None

    # node punya lat/lon langsung; way/relation punya "center"
    lat = el.get("lat") or el.get("center", {}).get("lat")
    lon = el.get("lon") or el.get("center", {}).get("lon")
    if lat is None or lon is None:
        return None

    nama = tags.get("name") or tags.get("name:id") or LABEL[kategori]
    deskripsi = tags.get("description") or tags.get("operator") or ""

    return {
        "id": f'{el["type"]}/{el["id"]}',
        "nama": nama,
        "kategori": kategori,
        "label": LABEL[kategori],
        "lat": lat,
        "lon": lon,
        "deskripsi": deskripsi,
        "sumber": f'https://www.openstreetmap.org/{el["type"]}/{el["id"]}',
    }


def ambil_titik_ui(paksa_refresh=False):
    """Ambil daftar titik strategis UI (dengan cache)."""
    if not paksa_refresh:
        data = cache.get(CACHE_KEY)
        if data is not None:
            return data

    s, w, n, e = BBOX
    try:
        resp = requests.post(
            OVERPASS_URL,
            data={"data": QUERY.format(s=s, w=w, n=n, e=e)},
            headers={"User-Agent": "Nebeng-kUI/1.0 (tugas kuliah)"},
            timeout=30,
        )
        resp.raise_for_status()
        elemen = resp.json().get("elements", [])
    except (requests.RequestException, ValueError):
        # kalau Overpass sedang down, pakai cache lama bila ada
        return cache.get(CACHE_KEY, [])

    hasil, terlihat = [], set()
    for el in elemen:
        item = _normalisasi(el)
        # buang duplikat (nama + kategori sama) agar daftar tidak berulang
        if item and (item["nama"], item["kategori"]) not in terlihat:
            terlihat.add((item["nama"], item["kategori"]))
            hasil.append(item)

    cache.set(CACHE_KEY, hasil, CACHE_TTL)
    return hasil


def tambah_jarak(titik, lat, lon):
    """Tambahkan field jarak_m dan urutkan dari yang terdekat."""
    for t in titik:
        t["jarak_m"] = round(haversine_km(lat, lon, t["lat"], t["lon"]) * 1000)
    return sorted(titik, key=lambda t: t["jarak_m"])

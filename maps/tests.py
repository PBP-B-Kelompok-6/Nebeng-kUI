import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from maps.models import CatatanPenjemputan, TitikKumpul

User = get_user_model()

def buat_user(username="budi"):
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="rahasia12345",
    )


def buat_titik(nama="Halte Fasilkom", kategori="halte", lat=-6.3650, lon=106.8280,
               aktif=True, osm_id=None):
    return TitikKumpul.objects.create(
        osm_id=osm_id or f"manual/{nama.lower().replace(' ', '-')}",
        nama=nama, kategori=kategori, lat=lat, lon=lon, aktif=aktif,
    )


def kirim_json(client_method, url, data):
    return client_method(url, data=json.dumps(data), content_type="application/json")


NODE_HALTE = {"type": "node", "id": 2, "lat": -6.3650, "lon": 106.8280,
              "tags": {"highway": "bus_stop", "name": "Halte Fasilkom"}}
NODE_STASIUN = {"type": "node", "id": 1, "lat": -6.3609, "lon": 106.8318,
                "tags": {"railway": "station", "name": "Stasiun UI"}}
WAY_PERPUS = {"type": "way", "id": 3, "center": {"lat": -6.3660, "lon": 106.8290},
              "tags": {"amenity": "library", "name": "Perpustakaan Pusat"}}
NODE_HALTE_DUPLIKAT = {"type": "node", "id": 4, "lat": -6.3651, "lon": 106.8281,
                       "tags": {"highway": "bus_stop", "name": "Halte Fasilkom"}}
NODE_TANPA_KATEGORI = {"type": "node", "id": 5, "lat": -6.36, "lon": 106.83,
                       "tags": {"shop": "bakery", "name": "Toko Roti"}}


class TitikKumpulModelTests(TestCase):
    def test_as_dict_berisi_field_yang_dibutuhkan_frontend(self):
        t = buat_titik("Stasiun UI", "stasiun")
        d = t.as_dict()
        self.assertEqual(
            set(d), {"pk", "id", "nama", "kategori", "label", "lat", "lon", "deskripsi"}
        )
        self.assertEqual(d["pk"], t.pk)
        self.assertEqual(d["id"], t.osm_id)
        self.assertEqual(d["label"], "Stasiun KRL")

    def test_str(self):
        self.assertEqual(str(buat_titik("Halte A", "halte")), "Halte A (Halte Bikun)")

    def test_aktif_default_true(self):
        self.assertTrue(buat_titik().aktif)

    def test_starred_by_dua_arah(self):
        user, t = buat_user(), buat_titik()
        t.starred_by.add(user)
        self.assertIn(t, user.starred_titik.all())
        self.assertIn(user, t.starred_by.all())


class CatatanModelTests(TestCase):
    def test_as_dict_dengan_titik(self):
        user, t = buat_user(), buat_titik("Stasiun UI", "stasiun")
        c = CatatanPenjemputan.objects.create(user=user, titik=t, teks="Tunggu di pilar biru")
        self.assertEqual(c.as_dict(), {
            "pk": c.pk, "teks": "Tunggu di pilar biru",
            "titik_pk": t.pk, "titik_nama": "Stasiun UI",
        })

    def test_as_dict_tanpa_titik(self):
        c = CatatanPenjemputan.objects.create(user=buat_user(), teks="Catatan umum")
        self.assertIsNone(c.as_dict()["titik_pk"])
        self.assertEqual(c.as_dict()["titik_nama"], "")

    def test_titik_dihapus_catatan_tetap_ada(self):
        user, t = buat_user(), buat_titik()
        c = CatatanPenjemputan.objects.create(user=user, titik=t, teks="x")
        t.delete()
        c.refresh_from_db()
        self.assertIsNone(c.titik)

    def test_user_dihapus_catatan_ikut_terhapus(self):
        user = buat_user()
        CatatanPenjemputan.objects.create(user=user, teks="x")
        user.delete()
        self.assertEqual(CatatanPenjemputan.objects.count(), 0)


class HalamanPetaTests(TestCase):
    def test_halaman_dapat_dibuka(self):
        resp = self.client.get(reverse("maps:halaman"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="map"')

    def test_hanya_method_get(self):
        self.assertEqual(self.client.post(reverse("maps:halaman")).status_code, 405)


class ApiToggleStarTests(TestCase):
    def setUp(self):
        self.user = buat_user()
        self.titik = buat_titik()
        self.url = reverse("maps:api_toggle_star", args=[self.titik.pk])

    def test_anonim_dialihkan_ke_login(self):
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.titik.starred_by.count(), 0)

    def test_toggle_menambah_lalu_menghapus(self):
        self.client.force_login(self.user)

        resp = self.client.post(self.url)
        self.assertEqual(resp.json(), {"starred": True, "jumlah": 1})
        self.assertTrue(self.titik.starred_by.filter(pk=self.user.pk).exists())

        resp = self.client.post(self.url)
        self.assertEqual(resp.json(), {"starred": False, "jumlah": 0})
        self.assertFalse(self.titik.starred_by.filter(pk=self.user.pk).exists())

    def test_favorit_antar_user_terpisah(self):
        lain = buat_user("lain")
        self.client.force_login(self.user)
        self.client.post(self.url)
        self.client.force_login(lain)
        resp = self.client.post(self.url)
        self.assertEqual(resp.json()["jumlah"], 2)

    def test_titik_nonaktif_tidak_bisa_di_star(self):
        self.titik.aktif = False
        self.titik.save()
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(self.url).status_code, 404)

    def test_titik_tidak_ada(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse("maps:api_toggle_star", args=[99999])).status_code, 404)

    def test_hanya_method_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 405)


class ApiCatatanTests(TestCase):
    def setUp(self):
        self.url = reverse("maps:api_catatan")
        self.user = buat_user()
        self.lain = buat_user("lain")
        self.titik = buat_titik("Stasiun UI", "stasiun")

    def _detail(self, pk):
        return reverse("maps:api_catatan_detail", args=[pk])

    # --- daftar
    def test_anonim_get_mengembalikan_daftar_kosong(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"hasil": [], "login": False})

    def test_daftar_hanya_milik_sendiri(self):
        CatatanPenjemputan.objects.create(user=self.user, teks="punyaku")
        CatatanPenjemputan.objects.create(user=self.lain, teks="punya orang")
        self.client.force_login(self.user)
        data = self.client.get(self.url).json()
        self.assertTrue(data["login"])
        self.assertEqual([c["teks"] for c in data["hasil"]], ["punyaku"])

    # --- buat
    def test_anonim_tidak_bisa_membuat(self):
        resp = kirim_json(self.client.post, self.url, {"teks": "x"})
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(CatatanPenjemputan.objects.count(), 0)

    def test_membuat_catatan_dengan_titik(self):
        self.client.force_login(self.user)
        resp = kirim_json(self.client.post, self.url, {"teks": "  Tunggu di pilar biru  ", "titik": self.titik.pk})
        self.assertEqual(resp.status_code, 201)
        c = CatatanPenjemputan.objects.get()
        self.assertEqual(c.user, self.user)
        self.assertEqual(c.teks, "Tunggu di pilar biru")   # spasi dipangkas
        self.assertEqual(c.titik, self.titik)
        self.assertEqual(resp.json()["catatan"]["titik_nama"], "Stasiun UI")

    def test_membuat_catatan_umum_tanpa_titik(self):
        self.client.force_login(self.user)
        resp = kirim_json(self.client.post, self.url, {"teks": "umum"})
        self.assertEqual(resp.status_code, 201)
        self.assertIsNone(CatatanPenjemputan.objects.get().titik)

    def test_titik_nonaktif_atau_tidak_ada_diabaikan(self):
        nonaktif = buat_titik("Mati", aktif=False)
        self.client.force_login(self.user)
        for pk in (nonaktif.pk, 99999):
            with self.subTest(pk=pk):
                resp = kirim_json(self.client.post, self.url, {"teks": "x", "titik": pk})
                self.assertEqual(resp.status_code, 201)
        self.assertEqual(CatatanPenjemputan.objects.filter(titik__isnull=True).count(), 2)

    def test_teks_kosong_ditolak(self):
        self.client.force_login(self.user)
        for teks in ("", "   "):
            with self.subTest(teks=teks):
                self.assertEqual(kirim_json(self.client.post, self.url, {"teks": teks}).status_code, 400)
        self.assertEqual(CatatanPenjemputan.objects.count(), 0)

    def test_teks_terlalu_panjang_ditolak(self):
        self.client.force_login(self.user)
        resp = kirim_json(self.client.post, self.url, {"teks": "a" * 301})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())

    def test_teks_tepat_batas_diterima(self):
        self.client.force_login(self.user)
        self.assertEqual(kirim_json(self.client.post, self.url, {"teks": "a" * 300}).status_code, 201)

    # --- ubah
    def test_mengubah_catatan_sendiri(self):
        c = CatatanPenjemputan.objects.create(user=self.user, teks="lama")
        self.client.force_login(self.user)
        resp = kirim_json(self.client.put, self._detail(c.pk), {"teks": "baru"})
        self.assertEqual(resp.status_code, 200)
        c.refresh_from_db()
        self.assertEqual(c.teks, "baru")

    def test_ubah_dengan_teks_kosong_ditolak(self):
        c = CatatanPenjemputan.objects.create(user=self.user, teks="lama")
        self.client.force_login(self.user)
        self.assertEqual(kirim_json(self.client.put, self._detail(c.pk), {"teks": ""}).status_code, 400)
        c.refresh_from_db()
        self.assertEqual(c.teks, "lama")

    def test_anonim_tidak_bisa_mengubah(self):
        c = CatatanPenjemputan.objects.create(user=self.user, teks="lama")
        self.assertEqual(kirim_json(self.client.put, self._detail(c.pk), {"teks": "x"}).status_code, 401)

    # --- hapus
    def test_menghapus_catatan_sendiri(self):
        c = CatatanPenjemputan.objects.create(user=self.user, teks="x")
        self.client.force_login(self.user)
        resp = self.client.delete(self._detail(c.pk))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"terhapus": True})
        self.assertFalse(CatatanPenjemputan.objects.filter(pk=c.pk).exists())

    def test_anonim_tidak_bisa_menghapus(self):
        c = CatatanPenjemputan.objects.create(user=self.user, teks="x")
        self.assertEqual(self.client.delete(self._detail(c.pk)).status_code, 401)
        self.assertTrue(CatatanPenjemputan.objects.filter(pk=c.pk).exists())

    def test_method_tidak_diizinkan(self):
        c = CatatanPenjemputan.objects.create(user=self.user, teks="x")
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self._detail(c.pk)).status_code, 405)
        self.assertEqual(self.client.patch(self.url).status_code, 405)
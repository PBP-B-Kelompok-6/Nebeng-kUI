"""
Unit test untuk app `reservasi` (models, views, urls).

Letakkan di: reservasi/tests.py   (atau reservasi/tests/test_reservasi.py)

Jalankan:
    python manage.py test reservasi

Coverage:
    pip install coverage
    coverage run --source=reservasi manage.py test reservasi
    coverage report -m
    coverage html
"""
import datetime
import decimal

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from forum.models import RidePost
from reservasi.models import PesanChat, Reservasi
from reservasi import views as reservasi_views
from users.models import RewardLog
from users.rewards import POINTS_PER_PASSENGER

User = get_user_model()
AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


# ---------------------------------------------------------------------------
# Helper pembuat data
# ---------------------------------------------------------------------------
def buat_user(username, password="pass12345"):
    # users_user.email bersifat UNIQUE, jadi tiap user wajib punya email berbeda
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password=password,
    )


def _nilai_default(field):
    """Isi otomatis field wajib RidePost agar test tidak rapuh terhadap
    perubahan skema model forum (field yang tidak kita ketahui)."""
    from django.db import models as m

    if field.choices:
        return field.choices[0][0]
    if isinstance(field, (m.CharField, m.TextField)):
        return "x"
    if isinstance(field, m.DateTimeField):
        return timezone.now() + datetime.timedelta(days=1)
    if isinstance(field, m.DateField):
        return timezone.now().date() + datetime.timedelta(days=1)
    if isinstance(field, m.TimeField):
        return datetime.time(8, 0)
    if isinstance(field, m.BooleanField):
        return False
    if isinstance(field, m.DecimalField):
        return decimal.Decimal("1")
    if isinstance(field, m.FloatField):
        return 1.0
    if isinstance(field, (m.IntegerField,)):
        return 1
    if isinstance(field, m.EmailField):
        return "a@example.com"
    raise ValueError(f"Field wajib {field.name} belum didukung helper; isi manual lewat kwargs.")


def buat_post(author, **kwargs):
    data = {
        "author": author,
        "pickup_point": "Halte UI",
        "departure_time": timezone.now() + datetime.timedelta(days=1),
        "max_quota": 2,
        "filled_quota": 0,
    }
    data.update(kwargs)
    for f in RidePost._meta.concrete_fields:
        if f.primary_key or f.auto_created or f.name in data:
            continue
        if f.has_default() or f.null or f.blank or getattr(f, "auto_now", False) or getattr(f, "auto_now_add", False):
            continue
        data[f.name] = _nilai_default(f)
    return RidePost.objects.create(**data)


def buat_reservasi(post, penumpang, status="DITERIMA", **kwargs):
    return Reservasi.objects.create(
        tebengan=post,
        penumpang=penumpang,
        status=status,
        titik_jemput=kwargs.pop("titik_jemput", "Halte UI"),
        waktu_jemput=kwargs.pop("waktu_jemput", timezone.now()),
        **kwargs,
    )


def buat_pesan(reservasi, pengirim, teks="halo", menit=0):
    """Buat pesan dengan timestamp eksplisit agar urutan 'terakhir' deterministik."""
    p = PesanChat.objects.create(reservasi=reservasi, pengirim=pengirim, teks=teks)
    PesanChat.objects.filter(pk=p.pk).update(
        timestamp=timezone.now() - datetime.timedelta(hours=1) + datetime.timedelta(minutes=menit)
    )
    p.refresh_from_db()
    return p


def pesan_flash(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


class BaseTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.driver = buat_user("driver")
        cls.penumpang = buat_user("penumpang")
        cls.orang_lain = buat_user("orang_lain")

    def setUp(self):
        self.post = buat_post(self.driver)


# ---------------------------------------------------------------------------
# MODELS
# ---------------------------------------------------------------------------
class ReservasiModelTest(BaseTest):
    def test_default_status_menunggu(self):
        r = Reservasi.objects.create(
            tebengan=self.post, penumpang=self.penumpang,
            titik_jemput="A", waktu_jemput=timezone.now(),
        )
        self.assertEqual(r.status, "MENUNGGU")
        self.assertIsNotNone(r.created_at)
        self.assertIsNotNone(r.updated_at)

    def test_str(self):
        r = buat_reservasi(self.post, self.penumpang, "DITERIMA")
        self.assertEqual(str(r), "Reservasi penumpang - DITERIMA")

    def test_chat_unlocked_per_status(self):
        hasil = {"MENUNGGU": False, "DITOLAK": False, "DITERIMA": True, "SELESAI": True}
        for status, harapan in hasil.items():
            r = Reservasi(status=status)
            self.assertEqual(r.chat_unlocked, harapan, status)

    def test_unique_constraint(self):
        buat_reservasi(self.post, self.penumpang, "MENUNGGU")
        with self.assertRaises(IntegrityError), transaction.atomic():
            buat_reservasi(self.post, self.penumpang, "MENUNGGU")

    def test_penumpang_sama_boleh_di_post_berbeda(self):
        post2 = buat_post(self.driver)
        buat_reservasi(self.post, self.penumpang)
        buat_reservasi(post2, self.penumpang)
        self.assertEqual(Reservasi.objects.filter(penumpang=self.penumpang).count(), 2)

    def test_tebengan_boleh_null(self):
        r = Reservasi.objects.create(
            tebengan=None, penumpang=self.penumpang,
            titik_jemput="A", waktu_jemput=timezone.now(),
        )
        self.assertIsNone(r.tebengan)

    def test_related_name_reservations_dan_cascade(self):
        r = buat_reservasi(self.post, self.penumpang)
        self.assertIn(r, self.post.reservations.all())
        self.post.delete()
        self.assertFalse(Reservasi.objects.filter(pk=r.pk).exists())


class PesanChatModelTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.res = buat_reservasi(self.post, self.penumpang)

    def test_str_dipotong_20_karakter(self):
        p = PesanChat.objects.create(reservasi=self.res, pengirim=self.penumpang, teks="a" * 50)
        self.assertEqual(str(p), "penumpang: " + "a" * 20)

    def test_str_pendek(self):
        p = PesanChat.objects.create(reservasi=self.res, pengirim=self.driver, teks="hai")
        self.assertEqual(str(p), "driver: hai")

    def test_ordering_terlama_ke_terbaru(self):
        p2 = buat_pesan(self.res, self.driver, "kedua", menit=10)
        p1 = buat_pesan(self.res, self.penumpang, "pertama", menit=1)
        p3 = buat_pesan(self.res, self.driver, "ketiga", menit=20)
        self.assertEqual(list(self.res.pesan_list.all()), [p1, p2, p3])

    def test_cascade_hapus_reservasi(self):
        buat_pesan(self.res, self.driver)
        self.res.delete()
        self.assertEqual(PesanChat.objects.count(), 0)


# ---------------------------------------------------------------------------
# HELPER VIEWS
# ---------------------------------------------------------------------------
class HelperViewTest(BaseTest):
    def test_chat_redirect(self):
        resp = reservasi_views._chat_redirect(7)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, f"{reverse('reservasi:show_reservasi')}?id=7")

    def test_is_participant(self):
        r = buat_reservasi(self.post, self.penumpang)
        self.assertTrue(reservasi_views._is_participant(self.penumpang, r))
        self.assertTrue(reservasi_views._is_participant(self.driver, r))
        self.assertFalse(reservasi_views._is_participant(self.orang_lain, r))

    def test_is_participant_tanpa_tebengan(self):
        r = Reservasi.objects.create(
            tebengan=None, penumpang=self.penumpang,
            titik_jemput="A", waktu_jemput=timezone.now(),
        )
        self.assertTrue(reservasi_views._is_participant(self.penumpang, r))
        self.assertFalse(reservasi_views._is_participant(self.driver, r))
        self.assertFalse(reservasi_views._is_participant(self.orang_lain, r))


# ---------------------------------------------------------------------------
# URLS
# ---------------------------------------------------------------------------
class UrlTest(TestCase):
    def test_reverse_semua_url(self):
        self.assertTrue(reverse("reservasi:show_reservasi"))
        self.assertTrue(reverse("reservasi:join", args=[1]))
        self.assertTrue(reverse("reservasi:decide", args=[1, "accept"]))
        self.assertTrue(reverse("reservasi:kirim_pesan", args=[1]))
        self.assertTrue(reverse("reservasi:edit_pesan", args=[1]))
        self.assertTrue(reverse("reservasi:hapus_pesan", args=[1]))
        self.assertTrue(reverse("reservasi:selesaikan_reservasi", args=[1]))

    def test_resolve_ke_view_yang_benar(self):
        from django.urls import resolve
        casing = {
            reverse("reservasi:show_reservasi"): reservasi_views.show_reservasi,
            reverse("reservasi:join", args=[1]): reservasi_views.join_post,
            reverse("reservasi:decide", args=[1, "accept"]): reservasi_views.decide_reservasi,
            reverse("reservasi:kirim_pesan", args=[1]): reservasi_views.kirim_pesan,
            reverse("reservasi:edit_pesan", args=[1]): reservasi_views.edit_pesan,
            reverse("reservasi:hapus_pesan", args=[1]): reservasi_views.hapus_pesan,
            reverse("reservasi:selesaikan_reservasi", args=[1]): reservasi_views.selesaikan_reservasi,
        }
        for url, view in casing.items():
            self.assertEqual(resolve(url).func, view, url)


# ---------------------------------------------------------------------------
# JOIN POST
# ---------------------------------------------------------------------------
class JoinPostTest(BaseTest):
    def url(self, post_id=None):
        return reverse("reservasi:join", args=[post_id or self.post.pk])

    def test_wajib_login(self):
        resp = self.client.post(self.url())
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)
        self.assertEqual(Reservasi.objects.count(), 0)

    def test_get_tidak_diizinkan(self):
        self.client.force_login(self.penumpang)
        self.assertEqual(self.client.get(self.url()).status_code, 405)

    def test_post_tidak_ditemukan(self):
        self.client.force_login(self.penumpang)
        self.assertEqual(self.client.post(self.url(99999)).status_code, 404)

    def test_join_sukses(self):
        self.client.force_login(self.penumpang)
        resp = self.client.post(self.url())
        self.assertRedirects(
            resp, reverse("forum:detail", kwargs={"pk": self.post.pk}),
            fetch_redirect_response=False,
        )
        r = Reservasi.objects.get(tebengan=self.post, penumpang=self.penumpang)
        self.assertEqual(r.status, "MENUNGGU")
        self.assertEqual(r.titik_jemput, self.post.pickup_point)
        self.assertEqual(r.waktu_jemput, self.post.departure_time)
        self.assertIn("Permintaan terkirim, menunggu persetujuan.", pesan_flash(resp))

    def test_join_duplikat(self):
        self.client.force_login(self.penumpang)
        self.client.post(self.url())
        resp = self.client.post(self.url())
        self.assertEqual(Reservasi.objects.count(), 1)
        self.assertIn("Kamu sudah pernah mengajukan di tumpangan ini.", pesan_flash(resp))

    def test_join_post_sendiri_non_ajax(self):
        self.client.force_login(self.driver)
        resp = self.client.post(self.url())
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Reservasi.objects.count(), 0)
        self.assertIn("Kamu tidak bisa nebeng di post sendiri.", pesan_flash(resp))

    def test_join_post_sendiri_ajax(self):
        self.client.force_login(self.driver)
        resp = self.client.post(self.url(), **AJAX)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["status"], "error")
        self.assertEqual(resp.json()["message"], "Kamu tidak bisa nebeng di post sendiri.")

    def _post_penuh(self):
        penuh = buat_post(self.driver, max_quota=1, filled_quota=1)  # save() -> status penuh
        self.assertNotEqual(penuh.status, RidePost.Status.AKTIF)
        return penuh

    def test_join_post_penuh_non_ajax(self):
        penuh = self._post_penuh()
        self.client.force_login(self.penumpang)
        resp = self.client.post(self.url(penuh.pk))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Reservasi.objects.count(), 0)
        self.assertIn("Tumpangan ini sudah penuh.", pesan_flash(resp))

    def test_join_post_penuh_ajax(self):
        penuh = self._post_penuh()
        self.client.force_login(self.penumpang)
        resp = self.client.post(self.url(penuh.pk), **AJAX)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["message"], "Tumpangan ini sudah penuh.")

    def test_next_url_aman_dipakai(self):
        self.client.force_login(self.penumpang)
        resp = self.client.post(self.url(), {"next": "/halaman/aman/"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, "/halaman/aman/")

    def test_next_url_berbahaya_diabaikan(self):
        self.client.force_login(self.penumpang)
        resp = self.client.post(self.url(), {"next": "https://evil.example.com/"})
        self.assertEqual(
            resp.url, reverse("forum:detail", kwargs={"pk": self.post.pk})
        )


# ---------------------------------------------------------------------------
# DECIDE RESERVASI
# ---------------------------------------------------------------------------
class DecideReservasiTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.res = buat_reservasi(self.post, self.penumpang, "MENUNGGU")

    def url(self, action, pk=None):
        return reverse("reservasi:decide", args=[pk or self.res.pk, action])

    def test_wajib_login(self):
        resp = self.client.post(self.url("accept"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_get_tidak_diizinkan(self):
        self.client.force_login(self.driver)
        self.assertEqual(self.client.get(self.url("accept")).status_code, 405)

    def test_bukan_pemilik_post_404(self):
        for user in (self.penumpang, self.orang_lain):
            self.client.force_login(user)
            self.assertEqual(self.client.post(self.url("accept")).status_code, 404)
        self.res.refresh_from_db()
        self.assertEqual(self.res.status, "MENUNGGU")

    def test_accept_non_ajax(self):
        self.client.force_login(self.driver)
        resp = self.client.post(self.url("accept"))
        self.assertRedirects(
            resp, reverse("forum:detail", kwargs={"pk": self.post.pk}),
            fetch_redirect_response=False,
        )
        self.res.refresh_from_db()
        self.post.refresh_from_db()
        self.assertEqual(self.res.status, "DITERIMA")
        self.assertEqual(self.post.filled_quota, 1)
        self.assertIn("Permintaan diterima. Chat sudah terbuka.", pesan_flash(resp))

    def test_accept_ajax(self):
        self.client.force_login(self.driver)
        resp = self.client.post(self.url("accept"), **AJAX)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "success", "action": "accept"})
        self.res.refresh_from_db()
        self.assertEqual(self.res.status, "DITERIMA")

    def test_accept_hingga_kuota_penuh_mengubah_status_post(self):
        post = buat_post(self.driver, max_quota=1)
        res = buat_reservasi(post, self.penumpang, "MENUNGGU")
        self.client.force_login(self.driver)
        self.client.post(self.url("accept", res.pk))
        post.refresh_from_db()
        self.assertEqual(post.filled_quota, 1)
        self.assertNotEqual(post.status, RidePost.Status.AKTIF)

    def _kuota_penuh(self):
        # Paksa filled == max tanpa lewat save() agar reservasi MENUNGGU tetap bisa diproses
        RidePost.objects.filter(pk=self.post.pk).update(filled_quota=self.post.max_quota)

    def test_accept_kuota_penuh_non_ajax(self):
        self._kuota_penuh()
        self.client.force_login(self.driver)
        resp = self.client.post(self.url("accept"))
        self.assertEqual(resp.status_code, 302)
        self.res.refresh_from_db()
        self.assertEqual(self.res.status, "MENUNGGU")
        self.assertIn("Kuota sudah penuh.", pesan_flash(resp))

    def test_accept_kuota_penuh_ajax(self):
        self._kuota_penuh()
        self.client.force_login(self.driver)
        resp = self.client.post(self.url("accept"), **AJAX)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["message"], "Kuota sudah penuh.")
        self.res.refresh_from_db()
        self.assertEqual(self.res.status, "MENUNGGU")

    def test_reject_non_ajax(self):
        self.client.force_login(self.driver)
        resp = self.client.post(self.url("reject"))
        self.assertEqual(resp.status_code, 302)
        self.res.refresh_from_db()
        self.post.refresh_from_db()
        self.assertEqual(self.res.status, "DITOLAK")
        self.assertEqual(self.post.filled_quota, 0)
        self.assertIn("Permintaan ditolak.", pesan_flash(resp))

    def test_reject_ajax(self):
        self.client.force_login(self.driver)
        resp = self.client.post(self.url("reject"), **AJAX)
        self.assertEqual(resp.json(), {"status": "success", "action": "reject"})
        self.res.refresh_from_db()
        self.assertEqual(self.res.status, "DITOLAK")

    def test_sudah_diproses_non_ajax(self):
        self.res.status = "DITERIMA"
        self.res.save()
        self.client.force_login(self.driver)
        resp = self.client.post(self.url("accept"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("Permintaan ini sudah diproses.", pesan_flash(resp))

    def test_sudah_diproses_ajax(self):
        self.res.status = "DITOLAK"
        self.res.save()
        self.client.force_login(self.driver)
        resp = self.client.post(self.url("reject"), **AJAX)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["message"], "Permintaan ini sudah diproses.")

    def test_action_tidak_dikenal_tidak_mengubah_apa_pun(self):
        self.client.force_login(self.driver)
        resp = self.client.post(self.url("ngawur"))
        self.assertEqual(resp.status_code, 302)
        self.res.refresh_from_db()
        self.assertEqual(self.res.status, "MENUNGGU")

    def test_action_tidak_dikenal_ajax(self):
        self.client.force_login(self.driver)
        resp = self.client.post(self.url("ngawur"), **AJAX)
        self.assertEqual(resp.json(), {"status": "success", "action": "ngawur"})
        self.res.refresh_from_db()
        self.assertEqual(self.res.status, "MENUNGGU")


# ---------------------------------------------------------------------------
# SHOW RESERVASI
# ---------------------------------------------------------------------------
class ShowReservasiTest(BaseTest):
    url = None

    def setUp(self):
        super().setUp()
        self.url = reverse("reservasi:show_reservasi")

    def test_wajib_login(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_kosong(self):
        self.client.force_login(self.penumpang)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "reservasi/chat.html")
        self.assertEqual(list(resp.context["daftar_reservasi"]), [])
        self.assertIsNone(resp.context["reservasi_aktif"])
        self.assertIsNone(resp.context["pesan_aktif"])

    def test_hanya_diterima_dan_selesai_baru(self):
        diterima = buat_reservasi(self.post, self.penumpang, "DITERIMA")
        p2, p3, p4 = (buat_post(self.driver) for _ in range(3))
        buat_reservasi(p2, self.penumpang, "MENUNGGU")
        buat_reservasi(p3, self.penumpang, "DITOLAK")
        selesai = buat_reservasi(p4, self.penumpang, "SELESAI")

        self.client.force_login(self.penumpang)
        resp = self.client.get(self.url)
        self.assertEqual(set(resp.context["daftar_reservasi"]), {diterima, selesai})

    def test_selesai_lama_diarsipkan(self):
        lama = buat_reservasi(self.post, self.penumpang, "SELESAI")
        Reservasi.objects.filter(pk=lama.pk).update(
            updated_at=timezone.now() - datetime.timedelta(hours=13)
        )
        self.client.force_login(self.penumpang)
        resp = self.client.get(self.url)
        self.assertEqual(list(resp.context["daftar_reservasi"]), [])

    def test_selesai_tepat_di_bawah_batas_masih_tampil(self):
        r = buat_reservasi(self.post, self.penumpang, "SELESAI")
        Reservasi.objects.filter(pk=r.pk).update(
            updated_at=timezone.now() - datetime.timedelta(hours=11)
        )
        self.client.force_login(self.penumpang)
        resp = self.client.get(self.url)
        self.assertEqual(list(resp.context["daftar_reservasi"]), [r])

    def test_driver_dan_penumpang_sama_sama_melihat(self):
        r = buat_reservasi(self.post, self.penumpang)
        for user in (self.driver, self.penumpang):
            self.client.force_login(user)
            resp = self.client.get(self.url)
            self.assertEqual(list(resp.context["daftar_reservasi"]), [r])

    def test_user_lain_tidak_melihat(self):
        buat_reservasi(self.post, self.penumpang)
        self.client.force_login(self.orang_lain)
        resp = self.client.get(self.url)
        self.assertEqual(list(resp.context["daftar_reservasi"]), [])
        self.assertIsNone(resp.context["reservasi_aktif"])

    def test_urutan_updated_at_terbaru_dulu_dan_default_aktif(self):
        p2 = buat_post(self.driver)
        lama = buat_reservasi(self.post, self.penumpang)
        baru = buat_reservasi(p2, self.penumpang)
        now = timezone.now()
        Reservasi.objects.filter(pk=lama.pk).update(updated_at=now - datetime.timedelta(hours=2))
        Reservasi.objects.filter(pk=baru.pk).update(updated_at=now - datetime.timedelta(hours=1))
        self.client.force_login(self.penumpang)
        resp = self.client.get(self.url)
        self.assertEqual(list(resp.context["daftar_reservasi"]), [baru, lama])
        self.assertEqual(resp.context["reservasi_aktif"], baru)

    def test_param_id_valid_memilih_reservasi(self):
        p2 = buat_post(self.driver)
        lama = buat_reservasi(self.post, self.penumpang)
        baru = buat_reservasi(p2, self.penumpang)
        Reservasi.objects.filter(pk=lama.pk).update(
            updated_at=timezone.now() - datetime.timedelta(hours=2)
        )
        self.client.force_login(self.penumpang)
        resp = self.client.get(self.url, {"id": lama.pk})
        self.assertEqual(resp.context["reservasi_aktif"], lama)

    def test_param_id_bukan_angka_fallback(self):
        r = buat_reservasi(self.post, self.penumpang)
        self.client.force_login(self.penumpang)
        resp = self.client.get(self.url, {"id": "abc"})
        self.assertEqual(resp.context["reservasi_aktif"], r)

    def test_param_id_tidak_dimiliki_fallback(self):
        mine = buat_reservasi(self.post, self.penumpang)
        post_lain = buat_post(self.orang_lain)
        punya_orang = buat_reservasi(post_lain, self.driver)  # bukan milik penumpang
        self.client.force_login(self.penumpang)
        resp = self.client.get(self.url, {"id": punya_orang.pk})
        self.assertEqual(resp.context["reservasi_aktif"], mine)

    def test_pesan_aktif_berisi_pesan_reservasi_aktif(self):
        r = buat_reservasi(self.post, self.penumpang)
        p1 = buat_pesan(r, self.penumpang, "a", 1)
        p2 = buat_pesan(r, self.driver, "b", 2)
        self.client.force_login(self.penumpang)
        resp = self.client.get(self.url)
        self.assertEqual(list(resp.context["pesan_aktif"]), [p1, p2])


# ---------------------------------------------------------------------------
# KIRIM PESAN
# ---------------------------------------------------------------------------
class KirimPesanTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.res = buat_reservasi(self.post, self.penumpang, "DITERIMA")
        self.url = reverse("reservasi:kirim_pesan", args=[self.res.pk])
        self.chat_url = f"{reverse('reservasi:show_reservasi')}?id={self.res.pk}"

    def test_wajib_login(self):
        resp = self.client.post(self.url, {"teks_pesan": "hi"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_reservasi_tidak_ada(self):
        self.client.force_login(self.penumpang)
        url = reverse("reservasi:kirim_pesan", args=[99999])
        self.assertEqual(self.client.post(url, {"teks_pesan": "hi"}).status_code, 404)

    def test_bukan_peserta_forbidden(self):
        self.client.force_login(self.orang_lain)
        resp = self.client.post(self.url, {"teks_pesan": "hi"})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(PesanChat.objects.count(), 0)

    def test_chat_terkunci_forbidden(self):
        for status in ("MENUNGGU", "DITOLAK"):
            Reservasi.objects.filter(pk=self.res.pk).update(status=status)
            self.client.force_login(self.penumpang)
            resp = self.client.post(self.url, {"teks_pesan": "hi"})
            self.assertEqual(resp.status_code, 403, status)
        self.assertEqual(PesanChat.objects.count(), 0)

    def test_kirim_non_ajax_penumpang(self):
        self.client.force_login(self.penumpang)
        resp = self.client.post(self.url, {"teks_pesan": "  halo  "})
        self.assertRedirects(resp, self.chat_url, fetch_redirect_response=False)
        p = PesanChat.objects.get()
        self.assertEqual(p.teks, "halo")
        self.assertEqual(p.pengirim, self.penumpang)
        self.assertEqual(p.reservasi, self.res)

    def test_kirim_non_ajax_driver(self):
        self.client.force_login(self.driver)
        self.client.post(self.url, {"teks_pesan": "otw"})
        self.assertEqual(PesanChat.objects.get().pengirim, self.driver)

    def test_kirim_ajax(self):
        self.client.force_login(self.penumpang)
        resp = self.client.post(self.url, {"teks_pesan": "halo"}, **AJAX)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        p = PesanChat.objects.get()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["pesan"]["id"], p.id)
        self.assertEqual(data["pesan"]["teks"], "halo")
        self.assertEqual(data["pesan"]["pengirim"], "penumpang")
        self.assertRegex(data["pesan"]["timestamp"], r"^\d{2}:\d{2}$")

    def test_kirim_setelah_selesai_masih_boleh(self):
        Reservasi.objects.filter(pk=self.res.pk).update(status="SELESAI")
        self.client.force_login(self.penumpang)
        self.client.post(self.url, {"teks_pesan": "makasih"})
        self.assertEqual(PesanChat.objects.count(), 1)

    def test_teks_kosong_atau_spasi_tidak_disimpan(self):
        self.client.force_login(self.penumpang)
        for payload in ({"teks_pesan": ""}, {"teks_pesan": "   "}, {}):
            resp = self.client.post(self.url, payload)
            self.assertRedirects(resp, self.chat_url, fetch_redirect_response=False)
        self.assertEqual(PesanChat.objects.count(), 0)

    def test_teks_kosong_ajax_redirect(self):
        self.client.force_login(self.penumpang)
        resp = self.client.post(self.url, {"teks_pesan": " "}, **AJAX)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(PesanChat.objects.count(), 0)

    def test_get_redirect_tanpa_membuat_pesan(self):
        self.client.force_login(self.penumpang)
        resp = self.client.get(self.url)
        self.assertRedirects(resp, self.chat_url, fetch_redirect_response=False)
        self.assertEqual(PesanChat.objects.count(), 0)


# ---------------------------------------------------------------------------
# EDIT PESAN
# ---------------------------------------------------------------------------
class EditPesanTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.res = buat_reservasi(self.post, self.penumpang, "DITERIMA")
        self.lama = buat_pesan(self.res, self.penumpang, "lama", 1)
        self.terakhir = buat_pesan(self.res, self.penumpang, "terakhir", 2)
        self.chat_url = f"{reverse('reservasi:show_reservasi')}?id={self.res.pk}"

    def url(self, p):
        return reverse("reservasi:edit_pesan", args=[p.pk])

    def test_wajib_login(self):
        resp = self.client.post(self.url(self.terakhir), {"teks_pesan_baru": "x"})
        self.assertIn("login", resp.url)

    def test_hanya_pengirim_yang_bisa_edit(self):
        self.client.force_login(self.driver)
        resp = self.client.post(self.url(self.terakhir), {"teks_pesan_baru": "x"})
        self.assertEqual(resp.status_code, 404)

    def test_pesan_tidak_ada(self):
        self.client.force_login(self.penumpang)
        url = reverse("reservasi:edit_pesan", args=[99999])
        self.assertEqual(self.client.post(url, {"teks_pesan_baru": "x"}).status_code, 404)

    def test_edit_terakhir_non_ajax(self):
        self.client.force_login(self.penumpang)
        resp = self.client.post(self.url(self.terakhir), {"teks_pesan_baru": "  baru  "})
        self.assertRedirects(resp, self.chat_url, fetch_redirect_response=False)
        self.terakhir.refresh_from_db()
        self.assertEqual(self.terakhir.teks, "baru")

    def test_edit_terakhir_ajax(self):
        self.client.force_login(self.penumpang)
        resp = self.client.post(self.url(self.terakhir), {"teks_pesan_baru": "baru"}, **AJAX)
        self.assertEqual(resp.json(), {"status": "success", "teks_baru": "baru"})
        self.terakhir.refresh_from_db()
        self.assertEqual(self.terakhir.teks, "baru")

    def test_edit_bukan_terakhir_non_ajax(self):
        self.client.force_login(self.penumpang)
        resp = self.client.post(self.url(self.lama), {"teks_pesan_baru": "baru"})
        self.assertRedirects(resp, self.chat_url, fetch_redirect_response=False)
        self.lama.refresh_from_db()
        self.assertEqual(self.lama.teks, "lama")
        self.assertIn("Hanya pesan terakhir yang bisa diedit.", pesan_flash(resp))

    def test_edit_bukan_terakhir_ajax(self):
        self.client.force_login(self.penumpang)
        resp = self.client.post(self.url(self.lama), {"teks_pesan_baru": "baru"}, **AJAX)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["message"], "Hanya pesan terakhir yang bisa diedit.")

    def test_edit_dianggap_bukan_terakhir_jika_lawan_bicara_membalas(self):
        buat_pesan(self.res, self.driver, "balasan", 3)
        self.client.force_login(self.penumpang)
        resp = self.client.post(self.url(self.terakhir), {"teks_pesan_baru": "baru"}, **AJAX)
        self.assertEqual(resp.status_code, 400)

    def test_teks_baru_kosong_tidak_mengubah(self):
        self.client.force_login(self.penumpang)
        for payload in ({"teks_pesan_baru": ""}, {"teks_pesan_baru": "  "}, {}):
            resp = self.client.post(self.url(self.terakhir), payload, **AJAX)
            self.assertEqual(resp.status_code, 302)
        self.terakhir.refresh_from_db()
        self.assertEqual(self.terakhir.teks, "terakhir")

    def test_get_hanya_redirect(self):
        self.client.force_login(self.penumpang)
        resp = self.client.get(self.url(self.terakhir))
        self.assertRedirects(resp, self.chat_url, fetch_redirect_response=False)
        self.terakhir.refresh_from_db()
        self.assertEqual(self.terakhir.teks, "terakhir")


# ---------------------------------------------------------------------------
# HAPUS PESAN
# ---------------------------------------------------------------------------
class HapusPesanTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.res = buat_reservasi(self.post, self.penumpang, "DITERIMA")
        self.lama = buat_pesan(self.res, self.penumpang, "lama", 1)
        self.terakhir = buat_pesan(self.res, self.penumpang, "terakhir", 2)
        self.chat_url = f"{reverse('reservasi:show_reservasi')}?id={self.res.pk}"

    def url(self, p):
        return reverse("reservasi:hapus_pesan", args=[p.pk])

    def test_wajib_login(self):
        resp = self.client.post(self.url(self.terakhir))
        self.assertIn("login", resp.url)
        self.assertEqual(PesanChat.objects.count(), 2)

    def test_hanya_pengirim(self):
        self.client.force_login(self.driver)
        self.assertEqual(self.client.post(self.url(self.terakhir)).status_code, 404)
        self.assertEqual(PesanChat.objects.count(), 2)

    def test_hapus_terakhir_non_ajax(self):
        self.client.force_login(self.penumpang)
        resp = self.client.post(self.url(self.terakhir))
        self.assertRedirects(resp, self.chat_url, fetch_redirect_response=False)
        self.assertFalse(PesanChat.objects.filter(pk=self.terakhir.pk).exists())
        self.assertTrue(PesanChat.objects.filter(pk=self.lama.pk).exists())

    def test_hapus_terakhir_ajax(self):
        self.client.force_login(self.penumpang)
        resp = self.client.post(self.url(self.terakhir), **AJAX)
        self.assertEqual(resp.json(), {"status": "success"})
        self.assertFalse(PesanChat.objects.filter(pk=self.terakhir.pk).exists())

    def test_hapus_bukan_terakhir_non_ajax(self):
        self.client.force_login(self.penumpang)
        resp = self.client.post(self.url(self.lama))
        self.assertRedirects(resp, self.chat_url, fetch_redirect_response=False)
        self.assertTrue(PesanChat.objects.filter(pk=self.lama.pk).exists())
        self.assertIn("Hanya pesan terakhir yang bisa ditarik.", pesan_flash(resp))

    def test_hapus_bukan_terakhir_ajax(self):
        self.client.force_login(self.penumpang)
        resp = self.client.post(self.url(self.lama), **AJAX)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["message"], "Hanya pesan terakhir yang bisa ditarik.")
        self.assertTrue(PesanChat.objects.filter(pk=self.lama.pk).exists())

    def test_get_tidak_menghapus(self):
        self.client.force_login(self.penumpang)
        resp = self.client.get(self.url(self.terakhir))
        self.assertRedirects(resp, self.chat_url, fetch_redirect_response=False)
        self.assertEqual(PesanChat.objects.count(), 2)

    def test_pesan_tidak_ada(self):
        self.client.force_login(self.penumpang)
        url = reverse("reservasi:hapus_pesan", args=[99999])
        self.assertEqual(self.client.post(url).status_code, 404)


# ---------------------------------------------------------------------------
# SELESAIKAN RESERVASI
# ---------------------------------------------------------------------------
class SelesaikanReservasiTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.res = buat_reservasi(self.post, self.penumpang, "DITERIMA")
        self.url = reverse("reservasi:selesaikan_reservasi", args=[self.res.pk])
        self.chat_url = f"{reverse('reservasi:show_reservasi')}?id={self.res.pk}"

    def test_wajib_login(self):
        resp = self.client.post(self.url)
        self.assertIn("login", resp.url)
        self.res.refresh_from_db()
        self.assertEqual(self.res.status, "DITERIMA")

    def test_get_hanya_redirect(self):
        self.client.force_login(self.driver)
        resp = self.client.get(self.url)
        self.assertRedirects(resp, self.chat_url, fetch_redirect_response=False)
        self.res.refresh_from_db()
        self.assertEqual(self.res.status, "DITERIMA")

    def test_reservasi_tidak_ada(self):
        self.client.force_login(self.driver)
        url = reverse("reservasi:selesaikan_reservasi", args=[99999])
        self.assertEqual(self.client.post(url).status_code, 404)

    def test_driver_selesaikan_non_ajax(self):
        poin_awal = User.objects.get(pk=self.driver.pk).reward_points
        self.client.force_login(self.driver)
        resp = self.client.post(self.url)
        self.assertRedirects(resp, self.chat_url, fetch_redirect_response=False)

        self.res.refresh_from_db()
        self.assertEqual(self.res.status, "SELESAI")
        self.assertEqual(
            User.objects.get(pk=self.driver.pk).reward_points,
            poin_awal + POINTS_PER_PASSENGER,
        )
        log = RewardLog.objects.get()
        self.assertEqual(log.user, self.driver)
        self.assertEqual(log.amount, POINTS_PER_PASSENGER)
        self.assertEqual(log.reason, "Menyelesaikan tebengan dengan penumpang")
        self.assertEqual(log.reference, f"reservation:{self.res.pk}")
        self.assertIn(
            f"Perjalanan selesai! Kamu mendapatkan {POINTS_PER_PASSENGER} poin reward.",
            pesan_flash(resp),
        )

    def test_driver_selesaikan_ajax(self):
        self.client.force_login(self.driver)
        resp = self.client.post(self.url, **AJAX)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "success", "message": "Perjalanan selesai!"})
        self.res.refresh_from_db()
        self.assertEqual(self.res.status, "SELESAI")
        self.assertEqual(RewardLog.objects.count(), 1)

    def test_penumpang_tidak_boleh_non_ajax(self):
        self.client.force_login(self.penumpang)
        resp = self.client.post(self.url)
        self.assertRedirects(resp, self.chat_url, fetch_redirect_response=False)
        self.res.refresh_from_db()
        self.assertEqual(self.res.status, "DITERIMA")
        self.assertEqual(RewardLog.objects.count(), 0)
        self.assertIn(
            "Kamu tidak memiliki hak untuk menyelesaikan perjalanan ini.", pesan_flash(resp)
        )

    def test_penumpang_tidak_boleh_ajax(self):
        self.client.force_login(self.penumpang)
        resp = self.client.post(self.url, **AJAX)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["message"], "Kamu tidak memiliki hak.")

    def test_orang_lain_tidak_boleh(self):
        self.client.force_login(self.orang_lain)
        resp = self.client.post(self.url, **AJAX)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(RewardLog.objects.count(), 0)

    def test_sudah_selesai_tidak_bisa_diulang_dan_tidak_double_poin(self):
        self.client.force_login(self.driver)
        self.client.post(self.url)
        poin = User.objects.get(pk=self.driver.pk).reward_points
        resp = self.client.post(self.url, **AJAX)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(RewardLog.objects.count(), 1)
        self.assertEqual(User.objects.get(pk=self.driver.pk).reward_points, poin)

    def test_status_menunggu_tidak_bisa_diselesaikan(self):
        Reservasi.objects.filter(pk=self.res.pk).update(status="MENUNGGU")
        self.client.force_login(self.driver)
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 302)
        self.res.refresh_from_db()
        self.assertEqual(self.res.status, "MENUNGGU")
        self.assertEqual(RewardLog.objects.count(), 0)
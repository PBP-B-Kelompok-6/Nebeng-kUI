"""
Unit test untuk app `forum` (models, forms, views, urls).

Letakkan di: forum/tests.py

Jalankan:
    python manage.py test forum

Coverage (pakai .coveragerc agar migrations/tests tidak ikut dihitung):
    coverage run --source=forum manage.py test forum
    coverage report -m
"""
import datetime
import decimal
import itertools
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.db import models as dj_models
from django.shortcuts import resolve_url
from django.test import TestCase
from django.urls import reverse, resolve
from django.utils import timezone

from forum import views
from forum.forms import RidePostForm
from forum.models import RidePost
from maps.models import TitikKumpul
from reservasi.models import Reservasi
from users.models import Vehicle

User = get_user_model()
AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
_counter = itertools.count(1)


# ---------------------------------------------------------------------------
# Helper pembuat data
# ---------------------------------------------------------------------------
def buat_user(username, password="pass12345"):
    # users_user.email bersifat UNIQUE -> email harus berbeda tiap user
    return User.objects.create_user(
        username=username, email=f"{username}@example.com", password=password
    )


def _nilai(field):
    """Nilai default untuk field wajib pada model app lain (Vehicle, TitikKumpul)
    yang strukturnya tidak diketahui; string dibuat unik."""
    m = dj_models
    if field.choices:
        return field.choices[0][0]
    if isinstance(field, (m.ForeignKey, m.OneToOneField)):
        related = field.remote_field.model
        if related is User:
            return buat_user(f"auto{next(_counter)}")
        return buat_objek(related)
    if isinstance(field, m.EmailField):
        return f"auto{next(_counter)}@example.com"
    if isinstance(field, (m.CharField, m.TextField)):
        return f"x{next(_counter)}"[: getattr(field, "max_length", None) or 50]
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
    if isinstance(field, m.IntegerField):
        return 1
    if isinstance(field, m.JSONField):
        return {}
    if isinstance(field, m.UUIDField):
        return uuid.uuid4()
    raise ValueError(
        f"Field wajib {field.model.__name__}.{field.name} belum didukung helper; "
        "isi manual lewat kwargs."
    )


def buat_objek(Model, **kwargs):
    data = dict(kwargs)
    for f in Model._meta.concrete_fields:
        if f.primary_key or f.auto_created or f.name in data:
            continue
        if (
            f.has_default() or f.null or f.blank
            or getattr(f, "auto_now", False) or getattr(f, "auto_now_add", False)
        ):
            continue
        data[f.name] = _nilai(f)
    return Model.objects.create(**data)


def buat_kendaraan(owner, capacity=4, **kwargs):
    return buat_objek(Vehicle, owner=owner, capacity=capacity, **kwargs)


def buat_titik(nama="Halte UI", aktif=True, **kwargs):
    return buat_objek(TitikKumpul, nama=nama, aktif=aktif, **kwargs)


def buat_post(author, **kwargs):
    data = {
        "author": author,
        "pickup_point": "Halte UI",
        "destination": "Kampus",
        "departure_time": timezone.now() + datetime.timedelta(days=1),
        "max_quota": 2,
        "filled_quota": 0,
    }
    data.update(kwargs)
    return RidePost.objects.create(**data)


def buat_reservasi(post, penumpang, status="MENUNGGU"):
    return Reservasi.objects.create(
        tebengan=post, penumpang=penumpang, status=status,
        titik_jemput="Halte UI", waktu_jemput=timezone.now(),
    )


def pesan_flash(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


class BaseTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.driver = buat_user("driver")
        cls.penumpang = buat_user("penumpang")

    def assertLoginRedirect(self, resp):
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.startswith(resolve_url(settings.LOGIN_URL)), resp.url)


# ---------------------------------------------------------------------------
# MODEL
# ---------------------------------------------------------------------------
class RidePostModelTest(BaseTest):
    def test_default_dan_status_aktif(self):
        p = buat_post(self.driver)
        self.assertEqual(p.status, RidePost.Status.AKTIF)
        self.assertIsNotNone(p.created_at)

    def test_default_field(self):
        p = RidePost.objects.create(
            author=self.driver, departure_time=timezone.now()
        )
        self.assertEqual(p.max_quota, 1)
        self.assertEqual(p.filled_quota, 0)
        self.assertEqual(p.notes, "")

    def test_seats_left(self):
        p = buat_post(self.driver, max_quota=4, filled_quota=1)
        self.assertEqual(p.seats_left, 3)

    def test_save_status_penuh_saat_kuota_terpenuhi(self):
        p = buat_post(self.driver, max_quota=2, filled_quota=2)
        self.assertEqual(p.status, RidePost.Status.PENUH)

    def test_save_status_penuh_saat_melebihi_kuota(self):
        p = buat_post(self.driver, max_quota=1, filled_quota=3)
        self.assertEqual(p.status, RidePost.Status.PENUH)

    def test_save_status_kembali_aktif(self):
        p = buat_post(self.driver, max_quota=2, filled_quota=2)
        p.filled_quota = 1
        p.save()
        p.refresh_from_db()
        self.assertEqual(p.status, RidePost.Status.AKTIF)

    def test_save_mengisi_pickup_dan_destination_dari_node(self):
        a = buat_titik("Stasiun UI")
        b = buat_titik("Margonda")
        p = buat_post(
            self.driver, pickup_point="lama", destination="lama",
            pickup_node=a, destination_node=b,
        )
        self.assertEqual(p.pickup_point, "Stasiun UI")
        self.assertEqual(p.destination, "Margonda")

    def test_save_tanpa_node_mempertahankan_teks(self):
        p = buat_post(self.driver, pickup_point="Manual A", destination="Manual B")
        self.assertEqual(p.pickup_point, "Manual A")
        self.assertEqual(p.destination, "Manual B")

    def test_save_hanya_pickup_node(self):
        a = buat_titik("Stasiun UI")
        p = buat_post(self.driver, pickup_node=a, destination="Tetap")
        self.assertEqual(p.pickup_point, "Stasiun UI")
        self.assertEqual(p.destination, "Tetap")

    def test_save_hanya_destination_node(self):
        b = buat_titik("Margonda")
        p = buat_post(self.driver, destination_node=b, pickup_point="Tetap")
        self.assertEqual(p.pickup_point, "Tetap")
        self.assertEqual(p.destination, "Margonda")

    def test_str(self):
        p = buat_post(self.driver, pickup_point="A", destination="B")
        self.assertEqual(str(p), "A → B")

    def test_ordering_terbaru_dulu(self):
        lama = buat_post(self.driver)
        baru = buat_post(self.driver)
        RidePost.objects.filter(pk=lama.pk).update(
            created_at=timezone.now() - datetime.timedelta(days=1)
        )
        self.assertEqual(list(RidePost.objects.all()), [baru, lama])

    def test_node_dihapus_set_null(self):
        a = buat_titik("Stasiun UI")
        p = buat_post(self.driver, pickup_node=a)
        a.delete()
        p.refresh_from_db()
        self.assertIsNone(p.pickup_node)

    def test_hapus_author_cascade(self):
        buat_post(self.driver)
        self.driver.delete()
        self.assertEqual(RidePost.objects.count(), 0)

    def test_related_name_ride_posts(self):
        p = buat_post(self.driver)
        self.assertIn(p, self.driver.ride_posts.all())


# ---------------------------------------------------------------------------
# FORM
# ---------------------------------------------------------------------------
class RidePostFormTest(BaseTest):
    def setUp(self):
        self.kendaraan = buat_kendaraan(self.driver)
        self.a = buat_titik("Stasiun UI")
        self.b = buat_titik("Margonda")

    def data(self, **extra):
        d = {
            "kendaraan": self.kendaraan.pk,
            "pickup_node": self.a.pk,
            "destination_node": self.b.pk,
            "departure_time": (
                timezone.localtime() + datetime.timedelta(days=1)
            ).strftime("%Y-%m-%dT%H:%M"),
            "notes": "Motor",
        }
        d.update(extra)
        return d

    def test_field_dan_label(self):
        form = RidePostForm(user=self.driver)
        self.assertEqual(
            list(form.fields),
            ["kendaraan", "pickup_node", "destination_node", "departure_time", "notes"],
        )
        self.assertEqual(form.fields["kendaraan"].label, "Kendaraan")
        self.assertEqual(form.fields["pickup_node"].label, "Titik jemput")
        self.assertEqual(form.fields["destination_node"].label, "Titik tujuan")
        self.assertEqual(form.fields["departure_time"].label, "Waktu berangkat")
        self.assertEqual(form.fields["notes"].label, "Catatan (opsional)")

    def test_widget_attrs(self):
        form = RidePostForm(user=self.driver)
        self.assertEqual(form.fields["notes"].widget.attrs["rows"], 3)
        self.assertEqual(form.fields["kendaraan"].widget.attrs["class"], "form-control")

    def test_empty_label_dan_required_node(self):
        form = RidePostForm(user=self.driver)
        self.assertEqual(form.fields["pickup_node"].empty_label, "-- Pilih Titik Jemput --")
        self.assertEqual(form.fields["destination_node"].empty_label, "-- Pilih Titik Tujuan --")
        self.assertTrue(form.fields["pickup_node"].required)
        self.assertTrue(form.fields["destination_node"].required)

    def test_node_hanya_yang_aktif(self):
        nonaktif = buat_titik("Tutup", aktif=False)
        form = RidePostForm(user=self.driver)
        for name in ("pickup_node", "destination_node"):
            qs = form.fields[name].queryset
            self.assertIn(self.a, qs)
            self.assertNotIn(nonaktif, qs)

    def test_kendaraan_difilter_per_user(self):
        milik_lain = buat_kendaraan(self.penumpang)
        qs = RidePostForm(user=self.driver).fields["kendaraan"].queryset
        self.assertIn(self.kendaraan, qs)
        self.assertNotIn(milik_lain, qs)

    def test_tanpa_user_kendaraan_tidak_difilter(self):
        milik_lain = buat_kendaraan(self.penumpang)
        qs = RidePostForm().fields["kendaraan"].queryset
        self.assertIn(self.kendaraan, qs)
        self.assertIn(milik_lain, qs)

    def test_data_valid(self):
        form = RidePostForm(self.data(), user=self.driver)
        self.assertTrue(form.is_valid(), form.errors)

    def test_notes_opsional(self):
        form = RidePostForm(self.data(notes=""), user=self.driver)
        self.assertTrue(form.is_valid(), form.errors)

    def test_kendaraan_tidak_wajib_di_level_form(self):
        d = self.data()
        d.pop("kendaraan")
        self.assertTrue(RidePostForm(d, user=self.driver).is_valid())

    def test_node_wajib(self):
        for name in ("pickup_node", "destination_node"):
            d = self.data()
            d.pop(name)
            form = RidePostForm(d, user=self.driver)
            self.assertFalse(form.is_valid())
            self.assertIn(name, form.errors)

    def test_departure_time_wajib(self):
        d = self.data()
        d.pop("departure_time")
        form = RidePostForm(d, user=self.driver)
        self.assertFalse(form.is_valid())
        self.assertIn("departure_time", form.errors)

    def test_kendaraan_milik_orang_lain_invalid(self):
        milik_lain = buat_kendaraan(self.penumpang)
        form = RidePostForm(self.data(kendaraan=milik_lain.pk), user=self.driver)
        self.assertFalse(form.is_valid())
        self.assertIn("kendaraan", form.errors)

    def test_node_nonaktif_invalid(self):
        nonaktif = buat_titik("Tutup", aktif=False)
        form = RidePostForm(self.data(pickup_node=nonaktif.pk), user=self.driver)
        self.assertFalse(form.is_valid())
        self.assertIn("pickup_node", form.errors)


# ---------------------------------------------------------------------------
# URL
# ---------------------------------------------------------------------------
class UrlTest(TestCase):
    def test_reverse_dan_resolve(self):
        casing = [
            (reverse("forum:feed"), views.FeedView),
            (reverse("forum:create"), views.PostCreateView),
            (reverse("forum:detail", kwargs={"pk": 1}), views.PostDetailView),
            (reverse("forum:delete", kwargs={"pk": 1}), views.PostDeleteView),
        ]
        for url, view in casing:
            self.assertEqual(resolve(url).func.view_class, view, url)


# ---------------------------------------------------------------------------
# FEED VIEW
# ---------------------------------------------------------------------------
class FeedViewTest(BaseTest):
    def setUp(self):
        self.url = reverse("forum:feed")

    def test_anonim_hanya_aktif_dan_mendatang(self):
        aktif = buat_post(self.driver)
        buat_post(self.driver, max_quota=1, filled_quota=1)  # penuh
        buat_post(self.driver, departure_time=timezone.now() - datetime.timedelta(hours=1))  # lewat
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "forum/feed.html")
        self.assertEqual(list(resp.context["posts"]), [aktif])
        self.assertFalse(resp.context["mine"])

    def test_urut_departure_time_terdekat_dulu(self):
        now = timezone.now()
        jauh = buat_post(self.driver, departure_time=now + datetime.timedelta(days=3))
        dekat = buat_post(self.driver, departure_time=now + datetime.timedelta(hours=2))
        tengah = buat_post(self.driver, departure_time=now + datetime.timedelta(days=1))
        resp = self.client.get(self.url)
        self.assertEqual(list(resp.context["posts"]), [dekat, tengah, jauh])

    def test_user_login_tanpa_mine_melihat_semua_aktif(self):
        p1 = buat_post(self.driver)
        p2 = buat_post(self.penumpang)
        self.client.force_login(self.penumpang)
        resp = self.client.get(self.url)
        self.assertEqual(set(resp.context["posts"]), {p1, p2})

    def test_mine_menampilkan_semua_post_sendiri_termasuk_penuh_dan_lewat(self):
        aktif = buat_post(self.driver)
        penuh = buat_post(self.driver, max_quota=1, filled_quota=1)
        lewat = buat_post(self.driver, departure_time=timezone.now() - datetime.timedelta(days=1))
        buat_post(self.penumpang)  # milik orang lain
        self.client.force_login(self.driver)
        resp = self.client.get(self.url, {"mine": "1"})
        self.assertEqual(set(resp.context["posts"]), {aktif, penuh, lewat})
        self.assertTrue(resp.context["mine"])

    def test_mine_selain_1_diabaikan(self):
        penuh = buat_post(self.driver, max_quota=1, filled_quota=1)
        self.client.force_login(self.driver)
        resp = self.client.get(self.url, {"mine": "0"})
        self.assertNotIn(penuh, resp.context["posts"])
        self.assertFalse(resp.context["mine"])

    def test_mine_anonim_tetap_feed_publik(self):
        aktif = buat_post(self.driver)
        penuh = buat_post(self.driver, max_quota=1, filled_quota=1)
        resp = self.client.get(self.url, {"mine": "1"})
        posts = list(resp.context["posts"])
        self.assertIn(aktif, posts)
        self.assertNotIn(penuh, posts)
        # perilaku saat ini: context['mine'] tetap True walau anonim
        self.assertTrue(resp.context["mine"])

    def test_pending_count(self):
        post = buat_post(self.driver, max_quota=5)
        u2, u3, u4 = buat_user("u2"), buat_user("u3"), buat_user("u4")
        buat_reservasi(post, self.penumpang, "MENUNGGU")
        buat_reservasi(post, u2, "MENUNGGU")
        buat_reservasi(post, u3, "DITERIMA")
        buat_reservasi(post, u4, "DITOLAK")
        kosong = buat_post(self.driver)
        resp = self.client.get(self.url)
        hasil = {p.pk: p.pending_count for p in resp.context["posts"]}
        self.assertEqual(hasil[post.pk], 2)
        self.assertEqual(hasil[kosong.pk], 0)

    def test_my_res_prefetch_untuk_user_login(self):
        post = buat_post(self.driver, max_quota=5)
        mine = buat_reservasi(post, self.penumpang)
        buat_reservasi(post, buat_user("lain"))
        tanpa = buat_post(self.driver)
        self.client.force_login(self.penumpang)
        resp = self.client.get(self.url)
        hasil = {p.pk: p.my_res for p in resp.context["posts"]}
        self.assertEqual(hasil[post.pk], [mine])
        self.assertEqual(hasil[tanpa.pk], [])

    def test_anonim_tidak_punya_my_res(self):
        buat_post(self.driver)
        resp = self.client.get(self.url)
        for p in resp.context["posts"]:
            self.assertFalse(hasattr(p, "my_res"))

    def test_kosong(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(list(resp.context["posts"]), [])


# ---------------------------------------------------------------------------
# DETAIL VIEW
# ---------------------------------------------------------------------------
class PostDetailViewTest(BaseTest):
    def setUp(self):
        self.post = buat_post(self.driver, max_quota=5)
        self.url = reverse("forum:detail", kwargs={"pk": self.post.pk})

    def test_404(self):
        resp = self.client.get(reverse("forum:detail", kwargs={"pk": 99999}))
        self.assertEqual(resp.status_code, 404)

    def test_anonim(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "forum/detail.html")
        self.assertEqual(resp.context["post"], self.post)
        self.assertNotIn("join_requests", resp.context)
        self.assertNotIn("my_reservation", resp.context)

    def test_author_melihat_join_requests(self):
        r1 = buat_reservasi(self.post, self.penumpang)
        r2 = buat_reservasi(self.post, buat_user("lain"), "DITERIMA")
        self.client.force_login(self.driver)
        resp = self.client.get(self.url)
        self.assertEqual(set(resp.context["join_requests"]), {r1, r2})
        self.assertNotIn("my_reservation", resp.context)

    def test_non_author_tanpa_reservasi(self):
        self.client.force_login(self.penumpang)
        resp = self.client.get(self.url)
        self.assertIsNone(resp.context["my_reservation"])
        self.assertNotIn("join_requests", resp.context)

    def test_non_author_dengan_reservasi(self):
        r = buat_reservasi(self.post, self.penumpang)
        buat_reservasi(self.post, buat_user("lain"))
        self.client.force_login(self.penumpang)
        resp = self.client.get(self.url)
        self.assertEqual(resp.context["my_reservation"], r)


# ---------------------------------------------------------------------------
# CREATE VIEW
# ---------------------------------------------------------------------------
class PostCreateViewTest(BaseTest):
    def setUp(self):
        self.url = reverse("forum:create")
        self.a = buat_titik("Stasiun UI")
        self.b = buat_titik("Margonda")

    def data(self, kendaraan, **extra):
        d = {
            "kendaraan": kendaraan.pk,
            "pickup_node": self.a.pk,
            "destination_node": self.b.pk,
            "departure_time": (
                timezone.localtime() + datetime.timedelta(days=1)
            ).strftime("%Y-%m-%dT%H:%M"),
            "notes": "Motor hitam",
        }
        d.update(extra)
        return d

    def test_anonim_get_dan_post_redirect_login(self):
        self.assertLoginRedirect(self.client.get(self.url))
        self.assertLoginRedirect(self.client.post(self.url, {}))
        self.assertEqual(RidePost.objects.count(), 0)

    def test_tanpa_kendaraan_redirect_ke_profil(self):
        self.client.force_login(self.driver)
        for method in (self.client.get, self.client.post):
            resp = method(self.url)
            self.assertRedirects(resp, reverse("users:profile"), fetch_redirect_response=False)
            self.assertIn(
                "Kamu harus mendaftarkan kendaraan terlebih dahulu sebelum bisa menawarkan tumpangan.",
                pesan_flash(resp),
            )
        self.assertEqual(RidePost.objects.count(), 0)

    def test_get_dengan_kendaraan(self):
        v = buat_kendaraan(self.driver)
        milik_lain = buat_kendaraan(self.penumpang)
        self.client.force_login(self.driver)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "forum/post_form.html")
        qs = resp.context["form"].fields["kendaraan"].queryset
        self.assertIn(v, qs)
        self.assertNotIn(milik_lain, qs)

    def test_post_valid_non_ajax(self):
        v = buat_kendaraan(self.driver, capacity=4)
        self.client.force_login(self.driver)
        resp = self.client.post(self.url, self.data(v))
        self.assertRedirects(resp, reverse("forum:feed"), fetch_redirect_response=False)
        p = RidePost.objects.get()
        self.assertEqual(p.author, self.driver)
        self.assertEqual(p.kendaraan, v)
        self.assertEqual(p.max_quota, 3)  # capacity - 1
        self.assertEqual(p.filled_quota, 0)
        self.assertEqual(p.pickup_point, "Stasiun UI")
        self.assertEqual(p.destination, "Margonda")
        self.assertEqual(p.notes, "Motor hitam")
        self.assertEqual(p.status, RidePost.Status.AKTIF)

    def test_kuota_minimal_1_untuk_kapasitas_kecil(self):
        self.client.force_login(self.driver)
        for cap in (1, 2):
            v = buat_kendaraan(self.driver, capacity=cap)
            self.client.post(self.url, self.data(v))
        self.assertEqual(
            list(RidePost.objects.order_by("id").values_list("max_quota", flat=True)),
            [1, 1],
        )

    def test_kuota_dari_kapasitas_besar(self):
        v = buat_kendaraan(self.driver, capacity=7)
        self.client.force_login(self.driver)
        self.client.post(self.url, self.data(v))
        self.assertEqual(RidePost.objects.get().max_quota, 6)

    def test_post_valid_ajax(self):
        v = buat_kendaraan(self.driver)
        self.client.force_login(self.driver)
        resp = self.client.post(self.url, self.data(v), **AJAX)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "success", "message": "Berhasil!"})
        self.assertEqual(RidePost.objects.count(), 1)

    def test_post_invalid_non_ajax_render_ulang_form(self):
        v = buat_kendaraan(self.driver)
        self.client.force_login(self.driver)
        resp = self.client.post(self.url, self.data(v, pickup_node=""))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "forum/post_form.html")
        self.assertIn("pickup_node", resp.context["form"].errors)
        self.assertEqual(RidePost.objects.count(), 0)

    def test_post_invalid_ajax_json_400(self):
        v = buat_kendaraan(self.driver)
        self.client.force_login(self.driver)
        resp = self.client.post(self.url, self.data(v, destination_node=""), **AJAX)
        self.assertEqual(resp.status_code, 400)
        body = resp.json()
        self.assertEqual(body["status"], "error")
        self.assertIn("destination_node", body["errors"])
        self.assertEqual(RidePost.objects.count(), 0)

    def test_kendaraan_milik_orang_lain_ditolak(self):
        buat_kendaraan(self.driver)  # agar lolos cek kendaraan
        milik_lain = buat_kendaraan(self.penumpang)
        self.client.force_login(self.driver)
        resp = self.client.post(self.url, self.data(milik_lain), **AJAX)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("kendaraan", resp.json()["errors"])
        self.assertEqual(RidePost.objects.count(), 0)


# ---------------------------------------------------------------------------
# DELETE VIEW
# ---------------------------------------------------------------------------
class PostDeleteViewTest(BaseTest):
    def setUp(self):
        self.post = buat_post(self.driver)
        self.url = reverse("forum:delete", kwargs={"pk": self.post.pk})

    def test_anonim_redirect_login(self):
        self.assertLoginRedirect(self.client.get(self.url))
        self.assertLoginRedirect(self.client.post(self.url))
        self.assertTrue(RidePost.objects.filter(pk=self.post.pk).exists())

    def test_non_author_forbidden(self):
        self.client.force_login(self.penumpang)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, **AJAX).status_code, 403)
        self.assertTrue(RidePost.objects.filter(pk=self.post.pk).exists())

    def test_post_tidak_ada(self):
        self.client.force_login(self.driver)
        url = reverse("forum:delete", kwargs={"pk": 99999})
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url).status_code, 404)

    def test_get_author_menampilkan_konfirmasi(self):
        self.client.force_login(self.driver)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "forum/post_confirm_delete.html")
        self.assertTrue(RidePost.objects.filter(pk=self.post.pk).exists())

    def test_hapus_non_ajax(self):
        self.client.force_login(self.driver)
        resp = self.client.post(self.url)
        self.assertRedirects(resp, reverse("forum:feed"), fetch_redirect_response=False)
        self.assertFalse(RidePost.objects.filter(pk=self.post.pk).exists())

    def test_hapus_ajax(self):
        self.client.force_login(self.driver)
        resp = self.client.post(self.url, **AJAX)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "success"})
        self.assertFalse(RidePost.objects.filter(pk=self.post.pk).exists())

    def test_hapus_post_ikut_menghapus_reservasi(self):
        r = buat_reservasi(self.post, self.penumpang)
        self.client.force_login(self.driver)
        self.client.post(self.url)
        self.assertFalse(Reservasi.objects.filter(pk=r.pk).exists())
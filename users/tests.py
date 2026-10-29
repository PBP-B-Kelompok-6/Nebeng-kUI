"""Test untuk app `users`.

Jalankan dengan:  python manage.py test users
"""
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from users.models import Redemption, RewardLog, User, Vehicle
from users.rewards import POINTS_PER_EXCHANGE, RUPIAH_PER_EXCHANGE

PASSWORD = "rahasia12345"
AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


def make_user(username, **extra):
    return User.objects.create_user(
        username=username, email=f"{username}@ui.ac.id", password=PASSWORD, **extra
    )


def make_vehicle(owner, plate, vtype="motor", name="Honda Vario 125", capacity=1):
    return Vehicle.objects.create(
        owner=owner, vehicle_type=vtype, name=name,
        plate_number=plate, capacity=capacity,
    )


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------
class UserModelTest(TestCase):
    def setUp(self):
        self.user = make_user("andrew", npm="2506656431")

    def test_str(self):
        self.assertEqual(str(self.user), "andrew")

    def test_default_points_and_balance_are_zero(self):
        self.assertEqual(self.user.reward_points, 0)
        self.assertEqual(self.user.balance, 0)

    def test_is_driver_depends_on_vehicle(self):
        self.assertFalse(self.user.is_driver)
        make_vehicle(self.user, "B 1111 AA")
        self.assertTrue(self.user.is_driver)

    def test_profile_picture_defaults_to_generated_avatar(self):
        self.assertTrue(
            self.user.profile_picture.startswith("https://ui-avatars.com/api/")
        )

    def test_custom_profile_picture_is_kept(self):
        user = make_user("budi", profile_picture="https://example.com/budi.png")
        self.assertEqual(user.profile_picture, "https://example.com/budi.png")

    def test_email_must_be_unique(self):
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                username="lain", email="andrew@ui.ac.id", password="x12345678"
            )


class VehicleModelTest(TestCase):
    def setUp(self):
        self.owner = make_user("andrew")

    def test_str(self):
        vehicle = make_vehicle(self.owner, "B 1111 AA")
        self.assertEqual(str(vehicle), "Honda Vario 125 (B 1111 AA)")

    def test_plate_is_normalized_on_save(self):
        for raw in ("b4567xyz", "b  4567  xyz", "B 4567 XYZ"):
            Vehicle.objects.all().delete()
            vehicle = make_vehicle(self.owner, raw)
            self.assertEqual(vehicle.plate_number, "B 4567 XYZ")

    def test_invalid_plate_fails_validation(self):
        vehicle = Vehicle(
            owner=self.owner, vehicle_type="motor", name="X",
            plate_number="123", capacity=1,
        )
        with self.assertRaises(ValidationError):
            vehicle.full_clean()

    def test_plate_must_be_unique(self):
        make_vehicle(self.owner, "B 1111 AA")
        with self.assertRaises(IntegrityError):
            make_vehicle(self.owner, "b1111aa")


# --------------------------------------------------------------------------
# Autentikasi
# --------------------------------------------------------------------------
class AuthFlowTest(TestCase):
    def setUp(self):
        self.user = make_user("andrew")

    def register_payload(self, **override):
        data = {
            "username": "baru", "email": "baru@ui.ac.id",
            "password1": "KataSandi!2026", "password2": "KataSandi!2026",
        }
        data.update(override)
        return data

    def login(self, **override):
        data = {"username": "andrew", "password": PASSWORD}
        data.update(override)
        return self.client.post(reverse("users:login"), data)

    def test_register_creates_user_with_hashed_password(self):
        response = self.client.post(reverse("users:register"), self.register_payload())
        self.assertRedirects(
            response, reverse("users:login"), fetch_redirect_response=False
        )
        new_user = User.objects.get(username="baru")
        self.assertNotEqual(new_user.password, "KataSandi!2026")
        self.assertTrue(new_user.check_password("KataSandi!2026"))

    def test_register_shows_success_message(self):
        response = self.client.post(
            reverse("users:register"), self.register_payload(), follow=True
        )
        self.assertContains(response, "Akun berhasil dibuat")

    def test_register_password_mismatch_rejected(self):
        response = self.client.post(
            reverse("users:register"),
            self.register_payload(password2="BedaSekali!2026"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="baru").exists())

    def test_register_duplicate_email_rejected(self):
        response = self.client.post(
            reverse("users:register"),
            self.register_payload(email="andrew@ui.ac.id"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="baru").exists())
        self.assertEqual(User.objects.filter(email="andrew@ui.ac.id").count(), 1)

    def test_login_success_sets_session_and_cookie(self):
        response = self.login()
        self.assertEqual(response.status_code, 302)
        self.assertIn("last_login", response.cookies)
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_wrong_password(self):
        response = self.login(password="salah")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_follows_safe_next(self):
        response = self.login(next=reverse("users:profile"))
        self.assertEqual(response.url, reverse("users:profile"))

    def test_login_ignores_unsafe_next(self):
        response = self.login(next="https://evil.example.com/")
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("evil.example.com", response.url)

    def test_login_page_keeps_next_in_form(self):
        response = self.client.get(reverse("users:login"), {"next": "/profile/"})
        self.assertContains(response, 'name="next" value="/profile/"')

    def test_logout_requires_post(self):
        self.client.login(username="andrew", password=PASSWORD)
        response = self.client.get(reverse("users:logout"))
        self.assertEqual(response.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

    def test_logout_clears_session_and_cookie(self):
        self.client.login(username="andrew", password=PASSWORD)
        response = self.client.post(reverse("users:logout"))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(response.cookies["last_login"].value, "")


class NavbarTest(TestCase):
    def setUp(self):
        make_user("andrew")

    def test_guest_sees_auth_links_and_no_account_menu(self):
        response = self.client.get(reverse("users:login"))
        self.assertContains(response, f'href="{reverse("users:register")}"')
        self.assertNotContains(response, 'id="user-menu-btn"')

    def test_logged_in_user_sees_account_menu(self):
        self.client.login(username="andrew", password=PASSWORD)
        response = self.client.get(reverse("users:profile"))
        self.assertContains(response, 'id="user-menu-btn"')
        self.assertContains(response, "@andrew")
        self.assertContains(response, f'action="{reverse("users:logout")}"')


# --------------------------------------------------------------------------
# Profil
# --------------------------------------------------------------------------
class ProfilePageTest(TestCase):
    def setUp(self):
        self.user = make_user(
            "andrew", first_name="Andrew", last_name="Chandra",
            npm="2506656431", faculty="Fakultas Ilmu Komputer",
        )
        make_vehicle(self.user, "b4567xyz")
        self.client.login(username="andrew", password=PASSWORD)
        self.url = reverse("users:profile")

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertRedirects(
            response, f"{reverse('users:login')}?next={self.url}",
            fetch_redirect_response=False,
        )

    def test_shows_user_data_and_vehicle(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/profile.html")
        for text in ("Andrew Chandra", "2506656431", "Fakultas Ilmu Komputer",
                     "B 4567 XYZ", "Motor", "1 kursi"):
            self.assertContains(response, text)

    def test_hides_other_users_vehicles(self):
        make_vehicle(make_user("lain"), "D 1234 AB", vtype="mobil", name="Toyota Yaris")
        response = self.client.get(self.url)
        self.assertNotContains(response, "D 1234 AB")
        self.assertNotContains(response, "Toyota Yaris")

    def test_eco_section_without_points(self):
        response = self.client.get(self.url)
        self.assertEqual(response.context["ride_count"], 0)
        self.assertEqual(response.context["exchange_lots"], 0)
        self.assertEqual(response.context["points_to_next"], POINTS_PER_EXCHANGE)
        self.assertEqual(response.context["progress_pct"], 0)
        self.assertContains(response, "Butuh 100 poin lagi")

    def test_eco_section_progress_toward_first_exchange(self):
        self.user.add_reward_points(50, reason="Uji", reference="seed:1")
        response = self.client.get(self.url)
        self.assertEqual(response.context["exchange_lots"], 0)
        self.assertEqual(response.context["points_to_next"], 50)
        self.assertEqual(response.context["progress_pct"], 50)

    def test_eco_section_with_enough_points(self):
        self.user.add_reward_points(250, reason="Uji", reference="seed:1")
        response = self.client.get(self.url)
        self.assertEqual(response.context["ride_count"], 1)
        self.assertEqual(response.context["exchange_lots"], 2)
        self.assertContains(response, "Tukar ke Saldo")


class ProfileEditTest(TestCase):
    def setUp(self):
        self.user = make_user(
            "andrew", npm="2506656431", faculty="Fakultas Ilmu Komputer"
        )
        self.client.login(username="andrew", password=PASSWORD)
        self.url = reverse("users:profile_edit")

    def payload(self, **override):
        data = {
            "first_name": "Andrew", "last_name": "Chandra",
            "npm": "2506656431", "phone_number": "",
            "faculty": "Fakultas Teknik", "bio": "", "profile_picture": "",
        }
        data.update(override)
        return data

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_page_renders_with_generic_form_template(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/form_page.html")

    def test_change_faculty_and_name(self):
        response = self.client.post(self.url, self.payload(first_name="Budi"))
        self.assertRedirects(
            response, reverse("users:profile"), fetch_redirect_response=False
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.faculty, "Fakultas Teknik")
        self.assertEqual(self.user.first_name, "Budi")

    def test_success_message_shown(self):
        response = self.client.post(self.url, self.payload(), follow=True)
        self.assertContains(response, "Profil berhasil diperbarui.")

    def test_invalid_npm_rejected(self):
        response = self.client.post(self.url, self.payload(npm="123"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "NPM harus 10 digit angka.")
        self.user.refresh_from_db()
        self.assertEqual(self.user.npm, "2506656431")

    def test_faculty_outside_list_rejected(self):
        response = self.client.post(self.url, self.payload(faculty="Fakultas Sihir"))
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.faculty, "Fakultas Ilmu Komputer")

    def test_email_cannot_be_changed_here(self):
        self.client.post(self.url, self.payload(email="baru@ui.ac.id"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "andrew@ui.ac.id")


# --------------------------------------------------------------------------
# CRUD kendaraan
# --------------------------------------------------------------------------
class VehicleCrudTest(TestCase):
    def setUp(self):
        self.user = make_user("andrew")
        self.other = make_user("lain")
        self.vehicle = make_vehicle(self.user, "b4567xyz")
        self.client.login(username="andrew", password=PASSWORD)

    def payload(self, **override):
        data = {
            "vehicle_type": "motor", "name": "Honda Beat",
            "plate_number": "B 1234 ABC", "capacity": 1,
        }
        data.update(override)
        return data

    def login_as_other(self):
        self.client.logout()
        self.client.login(username="lain", password=PASSWORD)

    def test_add_page_renders(self):
        response = self.client.get(reverse("users:vehicle_add"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/form_page.html")

    def test_create_sets_owner_and_normalizes_plate(self):
        response = self.client.post(
            reverse("users:vehicle_add"), self.payload(plate_number="b 1234 abc")
        )
        self.assertRedirects(
            response, reverse("users:profile"), fetch_redirect_response=False
        )
        vehicle = Vehicle.objects.get(name="Honda Beat")
        self.assertEqual(vehicle.owner, self.user)
        self.assertEqual(vehicle.plate_number, "B 1234 ABC")

    def test_create_shows_success_message(self):
        response = self.client.post(
            reverse("users:vehicle_add"), self.payload(), follow=True
        )
        self.assertContains(response, "Kendaraan berhasil ditambahkan.")

    def test_duplicate_plate_rejected_even_with_different_format(self):
        response = self.client.post(
            reverse("users:vehicle_add"), self.payload(plate_number="b4567xyz")
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pelat nomor ini sudah terdaftar.")
        self.assertEqual(Vehicle.objects.count(), 1)

    def test_invalid_plate_format_rejected(self):
        response = self.client.post(
            reverse("users:vehicle_add"), self.payload(plate_number="123")
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Vehicle.objects.count(), 1)

    def test_capacity_out_of_range_rejected(self):
        for capacity in (0, 9):
            response = self.client.post(
                reverse("users:vehicle_add"), self.payload(capacity=capacity)
            )
            self.assertEqual(response.status_code, 200)
        self.assertEqual(Vehicle.objects.count(), 1)

    def test_anonymous_cannot_create(self):
        self.client.logout()
        response = self.client.post(reverse("users:vehicle_add"), self.payload())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Vehicle.objects.count(), 1)

    def test_update_own_vehicle(self):
        url = reverse("users:vehicle_edit", args=[self.vehicle.pk])
        response = self.client.post(url, self.payload(
            vehicle_type="mobil", name="Toyota Yaris",
            plate_number="B 4567 XYZ", capacity=3,
        ))
        self.assertRedirects(
            response, reverse("users:profile"), fetch_redirect_response=False
        )
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.name, "Toyota Yaris")
        self.assertEqual(self.vehicle.capacity, 3)

    def test_update_keeping_own_plate_is_not_a_duplicate(self):
        url = reverse("users:vehicle_edit", args=[self.vehicle.pk])
        response = self.client.post(url, self.payload(plate_number="B 4567 XYZ"))
        self.assertEqual(response.status_code, 302)

    def test_cannot_edit_other_users_vehicle(self):
        self.login_as_other()
        url = reverse("users:vehicle_edit", args=[self.vehicle.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, self.payload()).status_code, 404)
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.name, "Honda Vario 125")

    def test_cannot_delete_other_users_vehicle(self):
        self.login_as_other()
        response = self.client.post(
            reverse("users:vehicle_delete", args=[self.vehicle.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Vehicle.objects.filter(pk=self.vehicle.pk).exists())

    def test_delete_requires_post(self):
        response = self.client.get(
            reverse("users:vehicle_delete", args=[self.vehicle.pk])
        )
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Vehicle.objects.filter(pk=self.vehicle.pk).exists())

    def test_anonymous_cannot_delete(self):
        self.client.logout()
        response = self.client.post(
            reverse("users:vehicle_delete", args=[self.vehicle.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Vehicle.objects.filter(pk=self.vehicle.pk).exists())

    def test_delete_own_vehicle(self):
        response = self.client.post(
            reverse("users:vehicle_delete", args=[self.vehicle.pk]), follow=True
        )
        self.assertFalse(Vehicle.objects.filter(pk=self.vehicle.pk).exists())
        self.assertContains(response, "Kendaraan berhasil dihapus.")


class VehicleFilterTest(TestCase):
    def setUp(self):
        self.user = make_user("andrew")
        other = make_user("lain")
        make_vehicle(self.user, "B 1111 AA", vtype="motor", name="Vario")
        make_vehicle(self.user, "B 2222 AA", vtype="motor", name="Beat")
        make_vehicle(self.user, "B 3333 AA", vtype="mobil", name="Yaris")
        make_vehicle(other, "B 4444 AA", vtype="mobil", name="Milik Lain")
        self.client.login(username="andrew", password=PASSWORD)
        self.url = reverse("users:profile")

    def names(self, response):
        return sorted(v.name for v in response.context["vehicles"])

    def test_no_filter_shows_only_own_vehicles(self):
        response = self.client.get(self.url)
        self.assertEqual(self.names(response), ["Beat", "Vario", "Yaris"])

    def test_filter_motor(self):
        response = self.client.get(self.url, {"vehicle_type": "motor"})
        self.assertEqual(self.names(response), ["Beat", "Vario"])

    def test_filter_mobil_excludes_other_users(self):
        response = self.client.get(self.url, {"vehicle_type": "mobil"})
        self.assertEqual(self.names(response), ["Yaris"])

    def test_invalid_filter_is_ignored(self):
        response = self.client.get(self.url, {"vehicle_type": "pesawat"})
        self.assertEqual(response.context["vehicle_filter"], "")
        self.assertEqual(len(self.names(response)), 3)

    def test_tab_counts(self):
        response = self.client.get(self.url)
        self.assertEqual(
            response.context["vehicle_tabs"],
            [("", "Semua", 3), ("motor", "Motor", 2), ("mobil", "Mobil", 1)],
        )

    def test_empty_result_message(self):
        Vehicle.objects.filter(owner=self.user, vehicle_type="mobil").delete()
        response = self.client.get(self.url, {"vehicle_type": "mobil"})
        self.assertContains(response, "Tidak ada kendaraan dengan jenis ini.")

    def test_ajax_returns_partial_only(self):
        response = self.client.get(self.url, {"vehicle_type": "motor"}, **AJAX)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/_vehicle_list.html")
        self.assertTemplateNotUsed(response, "users/profile.html")
        self.assertContains(response, "Vario")
        self.assertNotContains(response, "Yaris")
        self.assertNotContains(response, "<html")

    def test_ajax_requires_login(self):
        self.client.logout()
        response = self.client.get(self.url, {"vehicle_type": "motor"}, **AJAX)
        self.assertEqual(response.status_code, 302)

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(self.url, {"vehicle_type": "motor"})
        self.assertEqual(response.status_code, 302)


# --------------------------------------------------------------------------
# Reward dan penukaran
# --------------------------------------------------------------------------
class RewardPointsTest(TestCase):
    def setUp(self):
        self.driver = make_user("driver")

    def test_add_points_updates_total_and_creates_log(self):
        log = self.driver.add_reward_points(
            10, reason="FT → Stasiun UI", reference="reservation:1"
        )
        self.assertEqual(self.driver.reward_points, 10)
        self.assertEqual(log.amount, 10)
        self.assertEqual(log.reason, "FT → Stasiun UI")
        self.assertEqual(self.driver.reward_logs.count(), 1)

    def test_total_is_persisted(self):
        self.driver.add_reward_points(10, reference="reservation:1")
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.reward_points, 10)

    def test_same_reference_awarded_only_once(self):
        self.driver.add_reward_points(10, reference="reservation:1")
        again = self.driver.add_reward_points(10, reference="reservation:1")
        self.assertIsNone(again)
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.reward_points, 10)
        self.assertEqual(self.driver.reward_logs.count(), 1)

    def test_different_references_are_both_awarded(self):
        self.driver.add_reward_points(10, reference="reservation:1")
        self.driver.add_reward_points(10, reference="reservation:2")
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.reward_points, 20)
        self.assertEqual(self.driver.reward_logs.count(), 2)

    def test_same_reference_for_different_users_is_allowed(self):
        other = make_user("lain")
        self.driver.add_reward_points(10, reference="reservation:1")
        self.assertIsNotNone(other.add_reward_points(10, reference="reservation:1"))

    def test_blank_reference_is_not_deduplicated(self):
        self.driver.add_reward_points(10)
        self.driver.add_reward_points(10)
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.reward_points, 20)
        self.assertEqual(self.driver.reward_logs.count(), 2)

    def test_amount_must_be_positive(self):
        for amount in (0, -5):
            with self.assertRaises(ValueError):
                self.driver.add_reward_points(amount)
        self.assertEqual(RewardLog.objects.count(), 0)


class ExchangeTest(TestCase):
    def setUp(self):
        self.user = make_user("andrew")
        self.user.add_reward_points(250, reason="Uji", reference="seed:1")
        self.client.login(username="andrew", password=PASSWORD)
        self.url = reverse("users:redeem")

    def exchange(self, lots, **kwargs):
        return self.client.post(self.url, {"lots": lots}, **kwargs)

    def assert_nothing_changed(self):
        self.user.refresh_from_db()
        self.assertEqual(self.user.reward_points, 250)
        self.assertEqual(self.user.balance, 0)
        self.assertEqual(Redemption.objects.count(), 0)

    def test_exchange_one_lot(self):
        self.exchange(1)
        self.user.refresh_from_db()
        self.assertEqual(self.user.reward_points, 250 - POINTS_PER_EXCHANGE)
        self.assertEqual(self.user.balance, RUPIAH_PER_EXCHANGE)

    def test_exchange_multiple_lots(self):
        self.exchange(2)
        self.user.refresh_from_db()
        self.assertEqual(self.user.reward_points, 50)
        self.assertEqual(self.user.balance, 2 * RUPIAH_PER_EXCHANGE)

    def test_exchange_creates_approved_record(self):
        self.exchange(2)
        record = self.user.redemptions.get()
        self.assertEqual(record.points, 200)
        self.assertEqual(record.amount_rupiah, 10000)
        self.assertEqual(record.status, Redemption.Status.APPROVED)

    def test_exchange_does_not_touch_ride_count(self):
        self.exchange(1)
        response = self.client.get(reverse("users:profile"))
        self.assertEqual(response.context["ride_count"], 1)

    def test_cannot_exceed_points(self):
        self.exchange(3)                    # butuh 300 poin, punya 250
        self.assert_nothing_changed()

    def test_zero_negative_and_non_numeric_rejected(self):
        for value in ("0", "-1", "abc", "", "1.5"):
            response = self.exchange(value)
            self.assertEqual(response.status_code, 302)
        self.assert_nothing_changed()

    def test_huge_number_does_not_crash(self):
        response = self.exchange(10 ** 30)
        self.assertEqual(response.status_code, 302)
        self.assert_nothing_changed()

    def test_exchange_requires_post(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_exchange_requires_login(self):
        self.client.logout()
        response = self.exchange(1)
        self.assertEqual(response.status_code, 302)
        self.assert_nothing_changed()

    def test_success_message_shown(self):
        response = self.exchange(1, follow=True)
        self.assertContains(response, "Saldo kamu sekarang Rp 5.000")

    def test_failure_message_shown(self):
        response = self.exchange(3, follow=True)
        self.assertContains(response, "Poin kamu tidak cukup.")


# --------------------------------------------------------------------------
# Admin
# --------------------------------------------------------------------------
class AdminSmokeTest(TestCase):
    def setUp(self):
        User.objects.create_superuser("admin", "admin@ui.ac.id", PASSWORD)
        self.client.login(username="admin", password=PASSWORD)
        self.member = make_user("andrew")
        self.member.add_reward_points(10, reason="Uji", reference="seed:1")

    def test_changelists_load(self):
        for name in ("users_user", "users_redemption", "users_rewardlog"):
            response = self.client.get(reverse(f"admin:{name}_changelist"))
            self.assertEqual(response.status_code, 200, name)

    def test_user_change_page_loads(self):
        url = reverse("admin:users_user_change", args=[self.member.pk])
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_redemptions_cannot_be_added_manually(self):
        response = self.client.get(reverse("admin:users_redemption_add"))
        self.assertEqual(response.status_code, 403)
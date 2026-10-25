from django.db import IntegrityError
from django.test import TestCase

from users.models import User


class UserModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="andrew",
            email="andrew@ui.ac.id",
            password="rahasia12345",
            npm="2506656431",
        )

    def test_str(self):
        self.assertEqual(str(self.user), "andrew")

    def test_default_reward_points_is_zero(self):
        self.assertEqual(self.user.reward_points, 0)

    def test_add_reward_points(self):
        self.user.add_reward_points(10)
        self.user.refresh_from_db()
        self.assertEqual(self.user.reward_points, 10)

    def test_email_must_be_unique(self):
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                username="lain", email="andrew@ui.ac.id", password="x12345678"
            )

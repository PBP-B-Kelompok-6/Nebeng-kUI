import re
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models import F

# Create your models here.
class User(AbstractUser):
    email = models.EmailField(unique=True)
    npm = models.CharField(max_length=10, blank=True)
    phone_number = models.CharField(max_length=16, blank=True)
    faculty = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)
    profile_picture = models.URLField(blank=True)
    reward_points = models.PositiveIntegerField(default=0)
    balance = models.PositiveIntegerField("saldo (Rp)", default=0) #saldo

    # def save(self, *args, **kwargs):
    #     if not self.profile_picture:
    #         self.profile_picture = f"https://ui-avatars.com/api/?name={self.username}&background=5c00e6&color=fff"
    #     super().save(*args, **kwargs)

    def save(self, *args, **kwargs):
        if not self.profile_picture:
            query = urlencode({
                "name": self.get_full_name() or self.username,
                "background": "5c00e6",
                "color": "fff",
            })
            self.profile_picture = f"https://ui-avatars.com/api/?{query}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username

    @property
    def is_driver(self):
        #  buat nanti ada vehicle
        return self.vehicles.exists()

    def add_reward_points(self, amount, reason="", reference=""):
        if amount <= 0:
            raise ValueError("Jumlah poin harus lebih dari 0.")
        try:
            with transaction.atomic():
                log = RewardLog.objects.create(
                    user=self, amount=amount, reason=reason, reference=reference
                )
                type(self).objects.filter(pk=self.pk).update(
                    reward_points=F("reward_points") + amount
                )
        except IntegrityError:
            if not reference:
                raise
            return None
        self.refresh_from_db(fields=["reward_points"])
        return log

PLATE_REGEX = re.compile(r"^[A-Z]{1,2} \d{1,4}( [A-Z]{1,3})?$")


def normalize_plate(value: str) -> str:
    """'b4567xyz' / 'b  4567 xyz' -> 'B 4567 XYZ'."""
    value = re.sub(r"\s+", "", (value or "").upper())
    match = re.match(r"^([A-Z]{1,2})(\d{1,4})([A-Z]{0,3})$", value)
    if not match:
        return value
    prefix, number, suffix = match.groups()
    return f"{prefix} {number}" + (f" {suffix}" if suffix else "")


def validate_plate_number(value: str):
    if not PLATE_REGEX.match(normalize_plate(value)):
        raise ValidationError("Format pelat nomor tidak valid. Contoh: B 4567 XYZ")


class Vehicle(models.Model):
    class VehicleType(models.TextChoices):
        MOTOR = "motor", "Motor"
        MOBIL = "mobil", "Mobil"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vehicles",
    )
    vehicle_type = models.CharField(
        max_length=10, choices=VehicleType.choices, default=VehicleType.MOTOR
    )
    name = models.CharField(
        max_length=100, help_text="Merek dan model, contoh: Honda Vario 125"
    )
    plate_number = models.CharField(
        max_length=15, unique=True, validators=[validate_plate_number]
    )
    capacity = models.PositiveSmallIntegerField(
        default=1, help_text="Jumlah kursi kosong yang bisa ditawarkan"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.plate_number})"

    def clean(self):
        super().clean()
        if self.capacity < 1:
            raise ValidationError({"capacity": "Kapasitas minimal 1 kursi."})

    def save(self, *args, **kwargs):
        self.plate_number = normalize_plate(self.plate_number)
        super().save(*args, **kwargs)

class Redemption(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Menunggu"
        APPROVED = "approved", "Disetujui"
        REJECTED = "rejected", "Ditolak"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="redemptions",
    )
    points = models.PositiveIntegerField()
    amount_rupiah = models.PositiveIntegerField()
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} {self.points} poin ({self.get_status_display()})"

    @property
    def amount_display(self):
        return "Rp " + f"{self.amount_rupiah:,}".replace(",", ".")

class RewardLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reward_logs",
    )
    amount = models.PositiveIntegerField()
    reason = models.CharField(max_length=200, blank=True)
    reference = models.CharField(
        max_length=100, blank=True,
        help_text="Penanda sumber poin, contoh: reservation:12",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "reference"],
                condition=~models.Q(reference=""),
                name="unique_reward_per_reference",
            )
        ]

    def __str__(self):
        return f"{self.user} +{self.amount}"
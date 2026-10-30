from django.conf import settings
from django.db import models
from maps.models import TitikKumpul


class RidePost(models.Model):
    class Status(models.TextChoices):
        AKTIF = "aktif", "Aktif"
        PENUH = "penuh", "Penuh"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ride_posts"
    )
    pickup_point = models.CharField(max_length=200)
    destination = models.CharField(max_length=200)
    kendaraan = models.ForeignKey('users.Vehicle', on_delete=models.CASCADE, null=True, blank=True)
    departure_time = models.DateTimeField()
    max_quota = models.PositiveSmallIntegerField(default=1)
    filled_quota = models.PositiveSmallIntegerField(default=0)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.AKTIF)
    created_at = models.DateTimeField(auto_now_add=True)
    pickup_node = models.ForeignKey(
        TitikKumpul, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="pickup_posts"
    )
    destination_node = models.ForeignKey(
        TitikKumpul, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="destination_posts"
    )

    class Meta:
        ordering = ["-created_at"]

    @property
    def seats_left(self):
        return self.max_quota - self.filled_quota

    def save(self, *args, **kwargs):
        self.status = (
            self.Status.PENUH if self.filled_quota >= self.max_quota else self.Status.AKTIF
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.pickup_point} → {self.destination}"
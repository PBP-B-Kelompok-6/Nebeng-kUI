from django.db import models

# Create your models here.
from django.conf import settings
from django.db import models


class RidePost(models.Model):
    class PostType(models.TextChoices):
        CARI = "cari", "Mencari Tebengan"
        BERI = "beri", "Memberi Tebengan"

    class Status(models.TextChoices):
        AKTIF = "aktif", "Aktif"
        PENUH = "penuh", "Penuh"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ride_posts"
    )
    post_type = models.CharField(max_length=10, choices=PostType.choices)
    pickup_point = models.CharField(max_length=200)
    destination = models.CharField(max_length=200)
    departure_time = models.DateTimeField()
    max_quota = models.PositiveSmallIntegerField(default=1)
    filled_quota = models.PositiveSmallIntegerField(default=0)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.AKTIF)
    created_at = models.DateTimeField(auto_now_add=True)

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
        return f"{self.get_post_type_display()}: {self.pickup_point} → {self.destination}"
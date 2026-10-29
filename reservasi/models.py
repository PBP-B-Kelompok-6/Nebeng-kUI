from django.db import models
from django.conf import settings
# Impor model Tebengan dari app forum jika sudah ada
# from forum.models import Tebengan 

class Reservasi(models.Model):
    STATUS_CHOICES = [
        ('MENUNGGU', 'Menunggu'),
        ('DITERIMA', 'Diterima'),
        ('DITOLAK', 'Ditolak'),
        ('SELESAI', 'Selesai'),
    ]

    tebengan = models.ForeignKey(
        "forum.RidePost", on_delete=models.CASCADE,
        related_name="reservations", null=True, blank=True,
    )
    penumpang = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reservasi_penumpang'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='MENUNGGU')
    titik_jemput = models.CharField(max_length=255)
    waktu_jemput = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tebengan", "penumpang"], name="unique_join_per_post")
        ]

    @property
    def chat_unlocked(self):
        return self.status in ("DITERIMA", "SELESAI")

    def __str__(self):
        return f"Reservasi {self.penumpang.username} - {self.status}"

class PesanChat(models.Model):
    reservasi = models.ForeignKey(Reservasi, on_delete=models.CASCADE, related_name='pesan_list')
    pengirim = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    teks = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp'] # Memastikan chat selalu diurutkan dari yang terlama ke terbaru

    def __str__(self):
        return f"{self.pengirim.username}: {self.teks[:20]}"
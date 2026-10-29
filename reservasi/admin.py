from django.contrib import admin
from .models import Reservasi, PesanChat

# Mendaftarkan model Reservasi agar tampil lebih rapi di admin
@admin.register(Reservasi)
class ReservasiAdmin(admin.ModelAdmin):
    list_display = ('id', 'penumpang', 'status', 'titik_jemput', 'waktu_jemput')
    list_filter = ('status',)

# Mendaftarkan model PesanChat
@admin.register(PesanChat)
class PesanChatAdmin(admin.ModelAdmin):
    list_display = ('pengirim', 'reservasi', 'timestamp')
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Reservasi, PesanChat

@login_required(login_url='/login/') # Pastikan path login ini sesuai dengan url login di modul users-mu
def show_reservasi(request):
    # 1. Ambil semua data reservasi yang ada untuk ditampilkan di daftar kolom sebelah kiri
    daftar_reservasi = Reservasi.objects.all()

    # 2. Ambil 1 reservasi spesifik untuk ditampilkan riwayat chat-nya di kolom sebelah kanan
    reservasi_aktif = daftar_reservasi.first()
    
    # 3. Ambil semua pesan chat yang terikat dengan reservasi_aktif tersebut
    pesan_aktif = None
    if reservasi_aktif:
        # Kita menggunakan 'pesan_list' karena itu adalah related_name yang kita set di models.py
        pesan_aktif = reservasi_aktif.pesan_list.all()

    # 4. Bungkus semua data ke dalam dictionary context
    context = {
        'daftar_reservasi': daftar_reservasi,
        'reservasi_aktif': reservasi_aktif,
        'pesan_aktif': pesan_aktif,
    }
    
    # 5. Lemparkan datanya ke template HTML
    return render(request, 'reservasi/chat.html', context)
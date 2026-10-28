from django.shortcuts import render
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Reservasi, PesanChat
from django.contrib import messages

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

@login_required
def kirim_pesan(request, reservasi_id):
    if request.method == 'POST':
        reservasi = get_object_or_404(Reservasi, id=reservasi_id)
        teks = request.POST.get('teks_pesan')
        
        if teks and teks.strip():
            PesanChat.objects.create(
                reservasi=reservasi,
                pengirim=request.user,
                teks=teks.strip()
            )
    return redirect('reservasi:show_reservasi') # Sesuaikan dengan nama URL aslimu

@login_required
def edit_pesan(request, pesan_id):
    if request.method == 'POST':
        pesan = get_object_or_404(PesanChat, id=pesan_id, pengirim=request.user)
        
        # Validasi: Cek apakah ini benar-benar pesan paling terakhir di reservasi ini
        pesan_terakhir = PesanChat.objects.filter(reservasi=pesan.reservasi).latest('timestamp')
        
        if pesan == pesan_terakhir:
            teks_baru = request.POST.get('teks_pesan_baru')
            if teks_baru and teks_baru.strip():
                pesan.teks = teks_baru.strip()
                pesan.save()
        else:
            messages.error(request, "Hanya pesan terakhir yang bisa diedit.")
            
    return redirect('reservasi:show_reservasi') 

@login_required
def hapus_pesan(request, pesan_id):
    if request.method == 'POST':
        pesan = get_object_or_404(PesanChat, id=pesan_id, pengirim=request.user)
        
        # Validasi: Cek apakah ini benar-benar pesan paling terakhir
        pesan_terakhir = PesanChat.objects.filter(reservasi=pesan.reservasi).latest('timestamp')
        
        if pesan == pesan_terakhir:
            pesan.delete()
        else:
            messages.error(request, "Hanya pesan terakhir yang bisa ditarik.")
            
    return redirect('reservasi:show_reservasi')

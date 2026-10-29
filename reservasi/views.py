from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.utils import timezone
from datetime import timedelta

from forum.models import RidePost
from .models import Reservasi, PesanChat
from django.urls import reverse
from users.rewards import POINTS_PER_PASSENGER
from users.models import RewardLog



def _chat_redirect(reservasi_id):
    return redirect(f"{reverse('reservasi:show_reservasi')}?id={reservasi_id}")

def _is_participant(user, reservasi):
    return user == reservasi.penumpang or (
        reservasi.tebengan_id and user == reservasi.tebengan.author
    )


# ---------- JOIN / TERIMA / TOLAK ----------
@login_required
@require_POST
def join_post(request, post_id):
    post = get_object_or_404(RidePost, pk=post_id)
    if post.author == request.user:
        messages.error(request, "Kamu tidak bisa nebeng di post sendiri.")
    elif post.status != RidePost.Status.AKTIF:
        messages.error(request, "Tumpangan ini sudah penuh.")
    else:
        _, created = Reservasi.objects.get_or_create(
            tebengan=post,
            penumpang=request.user,
            defaults={
                "titik_jemput": post.pickup_point,
                "waktu_jemput": post.departure_time,
            },
        )
        if created:
            messages.success(request, "Permintaan terkirim, menunggu persetujuan.")
        else:
            messages.info(request, "Kamu sudah pernah mengajukan di tumpangan ini.")

    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("forum:detail", pk=post_id)


@login_required
@require_POST
def decide_reservasi(request, pk, action):
    with transaction.atomic():
        res = get_object_or_404(
            Reservasi.objects.select_related("tebengan"),
            pk=pk, tebengan__author=request.user,
        )
        if res.status != "MENUNGGU":
            messages.error(request, "Permintaan ini sudah diproses.")
        elif action == "accept":
            post = RidePost.objects.select_for_update().get(pk=res.tebengan_id)
            if post.filled_quota >= post.max_quota:
                messages.error(request, "Kuota sudah penuh.")
            else:
                post.filled_quota += 1
                post.save()  # status Penuh otomatis dari save()
                res.status = "DITERIMA"
                res.save()
                messages.success(request, "Permintaan diterima. Chat sudah terbuka.")
        elif action == "reject":
            res.status = "DITOLAK"
            res.save()
            messages.success(request, "Permintaan ditolak.")
    return redirect("forum:detail", pk=res.tebengan_id)

@login_required
def show_reservasi(request):
    batas_waktu_arsip = timezone.now() - timedelta(hours=12)
    daftar_reservasi = (
        Reservasi.objects
        # Munculkan jika statusnya DITERIMA, ATAU jika SELESAI tapi update-nya belum lewat 24 jam
        .filter(
            Q(status="DITERIMA") | 
            Q(status="SELESAI", updated_at__gte=batas_waktu_arsip)
        )
        .filter(Q(penumpang=request.user) | Q(tebengan__author=request.user))
        .select_related("penumpang", "tebengan", "tebengan__author")
        .order_by("-updated_at") # Urutkan berdasarkan interaksi terbaru
    )

    reservasi_aktif = None
    rid = request.GET.get("id")
    if rid and rid.isdigit():
        reservasi_aktif = daftar_reservasi.filter(pk=int(rid)).first()
    if reservasi_aktif is None:
        reservasi_aktif = daftar_reservasi.first()

    pesan_aktif = reservasi_aktif.pesan_list.all() if reservasi_aktif else None

    return render(request, 'reservasi/chat.html', {
        'daftar_reservasi': daftar_reservasi,
        'reservasi_aktif': reservasi_aktif,
        'pesan_aktif': pesan_aktif,
    })

@login_required
def kirim_pesan(request, reservasi_id):
    reservasi = get_object_or_404(Reservasi, id=reservasi_id)
    if not _is_participant(request.user, reservasi) or not reservasi.chat_unlocked:
        return HttpResponseForbidden()
    if request.method == 'POST':
        teks = request.POST.get('teks_pesan')
        if teks and teks.strip():
            PesanChat.objects.create(reservasi=reservasi, pengirim=request.user, teks=teks.strip())
    return _chat_redirect(reservasi_id)


@login_required
def edit_pesan(request, pesan_id):
    pesan = get_object_or_404(PesanChat, id=pesan_id, pengirim=request.user)
    if request.method == 'POST':
        pesan_terakhir = PesanChat.objects.filter(reservasi=pesan.reservasi).latest('timestamp')
        if pesan == pesan_terakhir:
            teks_baru = request.POST.get('teks_pesan_baru')
            if teks_baru and teks_baru.strip():
                pesan.teks = teks_baru.strip()
                pesan.save()
        else:
            messages.error(request, "Hanya pesan terakhir yang bisa diedit.")
    return _chat_redirect(pesan.reservasi_id)


@login_required
def hapus_pesan(request, pesan_id):
    pesan = get_object_or_404(PesanChat, id=pesan_id, pengirim=request.user)
    rid = pesan.reservasi_id
    if request.method == 'POST':
        pesan_terakhir = PesanChat.objects.filter(reservasi=pesan.reservasi).latest('timestamp')
        if pesan == pesan_terakhir:
            pesan.delete()
        else:
            messages.error(request, "Hanya pesan terakhir yang bisa ditarik.")
    return _chat_redirect(rid)

@login_required
def selesaikan_reservasi(request, reservasi_id):
    if request.method == 'POST':
        reservasi = get_object_or_404(Reservasi, id=reservasi_id)
        
        # Validasi: Hanya driver (pembuat tebengan) yang berstatus DITERIMA
        if request.user == reservasi.tebengan.author and reservasi.status == 'DITERIMA':
            # 1. Ubah status reservasi menjadi SELESAI
            reservasi.status = 'SELESAI'
            reservasi.save()
            
            # 2. Tambah poin ke user driver
            request.user.reward_points += POINTS_PER_PASSENGER
            request.user.save()
            
            # 3. Buat entri RewardLog sesuai field model users
            RewardLog.objects.create(
                user=request.user,
                amount=POINTS_PER_PASSENGER,
                reason=f"Menyelesaikan tebengan dengan {reservasi.penumpang.username}",
                reference=f"reservation:{reservasi.id}"
            )
            
            messages.success(request, f"Perjalanan selesai! Kamu mendapatkan {POINTS_PER_PASSENGER} poin reward.")
        else:
            messages.error(request, "Kamu tidak memiliki hak untuk menyelesaikan perjalanan ini.")
            
    return redirect(f"{reverse('reservasi:show_reservasi')}?id={reservasi_id}")
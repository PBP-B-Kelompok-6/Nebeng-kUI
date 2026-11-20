from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden, JsonResponse
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

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .serializers import ReservasiSerializer, PesanChatSerializer



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
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Kamu tidak bisa nebeng di post sendiri.'}, status=400)
    elif post.status != RidePost.Status.AKTIF:
        messages.error(request, "Tumpangan ini sudah penuh.")
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Tumpangan ini sudah penuh.'}, status=400)
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
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': 'Permintaan ini sudah diproses.'}, status=400)
        elif action == "accept":
            post = RidePost.objects.select_for_update().get(pk=res.tebengan_id)
            if post.filled_quota >= post.max_quota:
                messages.error(request, "Kuota sudah penuh.")
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'error', 'message': 'Kuota sudah penuh.'}, status=400)
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
            
    # RESPONS AJAX JIKA DIPANGGIL LEWAT JAVASCRIPT
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'action': action})
    
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
            pesan = PesanChat.objects.create(reservasi=reservasi, pengirim=request.user, teks=teks.strip())
            
            # Jika AJAX, kirim data pesan baru sebagai JSON
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'pesan': {
                        'id': pesan.id,
                        'teks': pesan.teks,
                        'pengirim': pesan.pengirim.username,
                        'timestamp': pesan.timestamp.strftime('%H:%M')
                    }
                })
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

                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'success', 'teks_baru': pesan.teks})
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': 'Hanya pesan terakhir yang bisa diedit.'}, status=400)
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
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success'})
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': 'Hanya pesan terakhir yang bisa ditarik.'}, status=400)
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
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success', 'message': 'Perjalanan selesai!'})
            
            messages.success(request, f"Perjalanan selesai! Kamu mendapatkan {POINTS_PER_PASSENGER} poin reward.")
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': 'Kamu tidak memiliki hak.'}, status=403)
            messages.error(request, "Kamu tidak memiliki hak untuk menyelesaikan perjalanan ini.")
            
    return redirect(f"{reverse('reservasi:show_reservasi')}?id={reservasi_id}")

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_reservasi_list(request):
    """
    Mengambil daftar reservasi milik user (sebagai penumpang maupun driver).
    - Default: DITERIMA atau SELESAI dalam 12 jam terakhir (sama seperti show_reservasi).
    - Query param ?all=true: menyertakan status MENUNGGU / DITOLAK.
    """
    queryset = (
        Reservasi.objects
        .filter(Q(penumpang=request.user) | Q(tebengan__author=request.user))
        .select_related("penumpang", "tebengan", "tebengan__author")
        .order_by("-updated_at")
    )

    if request.GET.get("all") != "true":
        batas_waktu_arsip = timezone.now() - timedelta(hours=12)
        queryset = queryset.filter(
            Q(status="DITERIMA") |
            Q(status="SELESAI", updated_at__gte=batas_waktu_arsip)
        )

    serializer = ReservasiSerializer(queryset, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_join_post(request, post_id):
    """
    Mengajukan reservasi nebeng pada suatu RidePost (ekivalen join_post).
    """
    post = get_object_or_404(RidePost, pk=post_id)

    if post.author == request.user:
        return Response(
            {'detail': 'Kamu tidak bisa nebeng di post sendiri.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if post.status != RidePost.Status.AKTIF:
        return Response(
            {'detail': 'Tumpangan ini sudah penuh.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    reservasi, created = Reservasi.objects.get_or_create(
        tebengan=post,
        penumpang=request.user,
        defaults={
            "titik_jemput": request.data.get("titik_jemput") or post.pickup_point,
            "waktu_jemput": request.data.get("waktu_jemput") or post.departure_time,
        },
    )

    if not created:
        return Response(
            {'detail': 'Kamu sudah pernah mengajukan di tumpangan ini.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = ReservasiSerializer(reservasi)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_decide_reservasi(request, pk):
    """
    Menerima atau menolak permintaan reservasi oleh driver (ekivalen decide_reservasi).
    Body JSON: {"action": "accept"} atau {"action": "reject"}
    """
    action = request.data.get("action")
    if action not in ("accept", "reject"):
        return Response(
            {'detail': 'Action harus bernilai "accept" atau "reject".'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        res = get_object_or_404(
            Reservasi.objects.select_related("tebengan"),
            pk=pk,
            tebengan__author=request.user,
        )
        if res.status != "MENUNGGU":
            return Response(
                {'detail': 'Permintaan ini sudah diproses.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if action == "accept":
            post = RidePost.objects.select_for_update().get(pk=res.tebengan_id)
            if post.filled_quota >= post.max_quota:
                return Response(
                    {'detail': 'Kuota sudah penuh.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            post.filled_quota += 1
            post.save()
            res.status = "DITERIMA"
            res.save()
        elif action == "reject":
            res.status = "DITOLAK"
            res.save()

    serializer = ReservasiSerializer(res)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_selesaikan_reservasi(request, reservasi_id):
    """
    Menyelesaikan perjalanan dan memberikan poin reward ke driver (ekivalen selesaikan_reservasi).
    """
    reservasi = get_object_or_404(Reservasi, id=reservasi_id)

    if request.user != reservasi.tebengan.author or reservasi.status != 'DITERIMA':
        return Response(
            {'detail': 'Kamu tidak memiliki hak untuk menyelesaikan perjalanan ini.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    with transaction.atomic():
        reservasi.status = 'SELESAI'
        reservasi.save()

        request.user.reward_points += POINTS_PER_PASSENGER
        request.user.save()

        RewardLog.objects.create(
            user=request.user,
            amount=POINTS_PER_PASSENGER,
            reason=f"Menyelesaikan tebengan dengan {reservasi.penumpang.username}",
            reference=f"reservation:{reservasi.id}",
        )

    serializer = ReservasiSerializer(reservasi)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_chat_list_create(request, reservasi_id):
    """
    GET  : Mengambil seluruh riwayat PesanChat pada suatu reservasi.
    POST : Mengirim PesanChat baru (ekivalen kirim_pesan).
    """
    reservasi = get_object_or_404(Reservasi, id=reservasi_id)

    if not _is_participant(request.user, reservasi):
        return Response(
            {'detail': 'Kamu bukan partisipan pada reservasi ini.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == 'GET':
        pesan_list = reservasi.pesan_list.select_related('pengirim').all()
        serializer = PesanChatSerializer(pesan_list, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == 'POST':
        if not reservasi.chat_unlocked:
            return Response(
                {'detail': 'Obrolan terkunci karena reservasi belum diterima.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = PesanChatSerializer(data=request.data)
        if serializer.is_valid():
            teks = serializer.validated_data.get('teks', '').strip()
            if not teks:
                return Response(
                    {'detail': 'Teks pesan tidak boleh kosong.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            pesan = serializer.save(
                reservasi=reservasi,
                pengirim=request.user,
                teks=teks,
            )
            return Response(
                PesanChatSerializer(pesan).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def api_chat_detail(request, pesan_id):
    """
    PATCH  : Mengedit teks pesan terakhir (ekivalen edit_pesan).
    DELETE : Menarik/menghapus pesan terakhir (ekivalen hapus_pesan).
    """
    pesan = get_object_or_404(PesanChat, id=pesan_id, pengirim=request.user)
    pesan_terakhir = PesanChat.objects.filter(reservasi=pesan.reservasi).latest('timestamp')

    if pesan != pesan_terakhir:
        return Response(
            {'detail': 'Hanya pesan terakhir yang dapat diubah atau ditarik.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if request.method == 'PATCH':
        teks_baru = request.data.get('teks', '').strip()
        if not teks_baru:
            return Response(
                {'detail': 'Teks pesan tidak boleh kosong.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        pesan.teks = teks_baru
        pesan.save()
        return Response(PesanChatSerializer(pesan).data, status=status.HTTP_200_OK)

    elif request.method == 'DELETE':
        pesan.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
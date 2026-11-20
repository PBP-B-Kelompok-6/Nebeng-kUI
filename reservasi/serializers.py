from rest_framework import serializers
from .models import Reservasi, PesanChat


class ReservasiSerializer(serializers.ModelSerializer):
    penumpang_username = serializers.CharField(
        source='penumpang.username', read_only=True
    )
    driver_username = serializers.CharField(
        source='tebengan.author.username', read_only=True, default=None
    )
    chat_unlocked = serializers.BooleanField(read_only=True)

    class Meta:
        model = Reservasi
        fields = [
            'id',
            'tebengan',
            'penumpang',
            'penumpang_username',
            'driver_username',
            'status',
            'chat_unlocked',
            'titik_jemput',
            'waktu_jemput',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'penumpang',
            'status',
            'chat_unlocked',
            'created_at',
            'updated_at',
        ]


class PesanChatSerializer(serializers.ModelSerializer):
    pengirim_username = serializers.CharField(
        source='pengirim.username', read_only=True
    )

    class Meta:
        model = PesanChat
        fields = [
            'id',
            'reservasi',
            'pengirim',
            'pengirim_username',
            'teks',
            'timestamp',
        ]
        read_only_fields = [
            'id',
            'reservasi',
            'pengirim',
            'timestamp',
        ]
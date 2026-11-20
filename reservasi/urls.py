from django.urls import path
from reservasi.views import *

app_name = "reservasi"

urlpatterns = [
    path("reservasi/", show_reservasi, name="show_reservasi"),
    path("join/<int:post_id>/", join_post, name="join"),
    path("keputusan/<int:pk>/<str:action>/", decide_reservasi, name="decide"),
    path('chat/kirim/<int:reservasi_id>/', kirim_pesan, name='kirim_pesan'),
    path('chat/edit/<int:pesan_id>/', edit_pesan, name='edit_pesan'),
    path('chat/hapus/<int:pesan_id>/', hapus_pesan, name='hapus_pesan'),
    path('selesai/<int:reservasi_id>/', selesaikan_reservasi, name='selesaikan_reservasi'),
    # --- Endpoint DRF (JSON) ---
    path('api/reservasi/', api_reservasi_list, name='api_reservasi_list'),
    path('api/reservasi/join/<int:post_id>/', api_join_post, name='api_join_post'),
    path('api/reservasi/<int:pk>/decide/', api_decide_reservasi, name='api_decide_reservasi'),
    path('api/reservasi/<int:reservasi_id>/selesaikan/', api_selesaikan_reservasi, name='api_selesaikan_reservasi'),
    path('api/reservasi/<int:reservasi_id>/chat/', api_chat_list_create, name='api_chat_list_create'),
    path('api/chat/<int:pesan_id>/', api_chat_detail, name='api_chat_detail'),
]
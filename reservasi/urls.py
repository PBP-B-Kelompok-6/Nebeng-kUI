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
]
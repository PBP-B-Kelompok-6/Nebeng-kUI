from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F

from users.models import Redemption, User

POINTS_PER_PASSENGER = 10      # poin flat per penumpang selesai (dipanggil modul reservasi)
POINTS_PER_EXCHANGE = 100      # satu paket penukaran
RUPIAH_PER_EXCHANGE = 5000     # nilai satu paket
MAX_LOTS_PER_REQUEST = 10_000


def format_rupiah(amount):
    return "Rp " + f"{amount:,}".replace(",", ".")


def exchange_points(user, lots):
    """Tukar `lots` paket (kelipatan 100 poin) menjadi saldo.

    Poin dipotong dan saldo ditambah dalam satu UPDATE bersyarat,
    jadi aman dari race condition dan saldo poin tidak bisa negatif.
    """
    if lots < 1:
        raise ValidationError(f"Minimal tukar 1 paket ({POINTS_PER_EXCHANGE} poin).")
    if lots > MAX_LOTS_PER_REQUEST:
        raise ValidationError("Poin kamu tidak cukup.")

    points = lots * POINTS_PER_EXCHANGE
    rupiah = lots * RUPIAH_PER_EXCHANGE
    with transaction.atomic():
        updated = User.objects.filter(
            pk=user.pk, reward_points__gte=points
        ).update(
            reward_points=F("reward_points") - points,
            balance=F("balance") + rupiah,
        )
        if not updated:
            raise ValidationError("Poin kamu tidak cukup.")
        redemption = Redemption.objects.create(
            user=user,
            points=points,
            amount_rupiah=rupiah,
            status=Redemption.Status.APPROVED,
        )
    user.refresh_from_db(fields=["reward_points", "balance"])
    return redemption
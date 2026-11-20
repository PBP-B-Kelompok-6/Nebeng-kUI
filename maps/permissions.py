"""maps/permissions.py"""
from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsSuperuserOrReadOnly(BasePermission):
    """Semua pengunjung boleh membaca; hanya superuser yang boleh mengubah titik."""

    message = "Hanya pemilik situs yang dapat mengubah titik kumpul."

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or request.user.is_superuser

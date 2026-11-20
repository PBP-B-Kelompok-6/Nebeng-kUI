from django.contrib.auth import authenticate, login, logout
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from users.authentication import MobileSessionAuthentication
from users.models import Vehicle
from users.serializers import (
    RegisterSerializer, UserProfileSerializer, VehicleSerializer,
)


# ---------- Auth ----------

@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {
                "status": False,
                "message": "Registrasi gagal.",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    user = serializer.save()
    return Response(
        {
            "status": True,
            "username": user.username,
            "message": "Akun berhasil dibuat. Silakan login.",
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def login_user(request):
    user = authenticate(
        request,
        username=request.data.get("username", ""),
        password=request.data.get("password", ""),
    )
    if user is None or not user.is_active:
        return Response(
            {"status": False, "message": "Username atau password salah."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    login(request, user) 
    return Response(
        {"status": True, "username": user.username, "message": "Login sukses!"}
    )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def logout_user(request):
    logout(request)
    return Response({"status": True, "message": "Logout sukses!"})


# ---------- Profil ----------

@api_view(["GET", "HEAD", "PATCH"])
@authentication_classes([MobileSessionAuthentication])
@permission_classes([IsAuthenticated])
def profile_detail(request):
    if request.method in ("GET", "HEAD"):
        serializer = UserProfileSerializer(request.user, context={"request": request})
        return Response(serializer.data)

    serializer = UserProfileSerializer(
        request.user, data=request.data, partial=True, context={"request": request},
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


# ---------- Kendaraan ----------

@api_view(["GET", "HEAD", "POST"])
@authentication_classes([MobileSessionAuthentication])
@permission_classes([IsAuthenticated])
def vehicle_list(request):
    if request.method in ("GET", "HEAD"):
        vehicles = Vehicle.objects.filter(owner=request.user)
        serializer = VehicleSerializer(
            vehicles, many=True, context={"request": request},
        )
        return Response(serializer.data)

    serializer = VehicleSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    serializer.save(owner=request.user)  # owner dari sesi, bukan dari klien
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET", "HEAD", "PUT", "PATCH", "DELETE"])
@authentication_classes([MobileSessionAuthentication])
@permission_classes([IsAuthenticated])
def vehicle_detail(request, vehicle_id):
    # Queryset dibatasi ke milik sendiri: kendaraan orang lain -> 404.
    vehicle = get_object_or_404(Vehicle, pk=vehicle_id, owner=request.user)

    if request.method in ("GET", "HEAD"):
        serializer = VehicleSerializer(vehicle, context={"request": request})
        return Response(serializer.data)

    if request.method == "DELETE":
        vehicle.delete()  # promosi kendaraan utama ditangani Vehicle.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = VehicleSerializer(
        vehicle, data=request.data, partial=request.method == "PATCH",
        context={"request": request},
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.html import strip_tags
from rest_framework import serializers

from users.models import User, Vehicle, normalize_plate
from users.models import validate_plate_number as check_plate_format


class RegisterSerializer(serializers.ModelSerializer):
    password1 = serializers.CharField(write_only=True, style={"input_type": "password"})
    password2 = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = [
            "username", "email", "first_name", "last_name", "npm",
            "password1", "password2",
        ]

    def validate(self, attrs):
        if attrs["password1"] != attrs["password2"]:
            raise serializers.ValidationError(
                {"password2": "Konfirmasi password tidak cocok."}
            )
        # Objek User sementara agar validator "mirip username/email" ikut bekerja.
        candidate = User(
            username=attrs["username"],
            email=attrs["email"],
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
        )
        try:
            validate_password(attrs["password1"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password1": list(exc.messages)})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password1")
        validated_data.pop("password2")
        return User.objects.create_user(password=password, **validated_data)


class UserProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    is_driver = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "first_name", "last_name", "full_name",
            "npm", "phone_number", "faculty", "bio", "profile_picture",
            "reward_points", "is_driver",
        ]
        # reward_points hanya berubah lewat User.add_reward_points() di server.
        read_only_fields = ["id", "username", "email", "reward_points"]

    def validate_first_name(self, value):
        return strip_tags(value).strip()

    def validate_last_name(self, value):
        return strip_tags(value).strip()

    def validate_faculty(self, value):
        return strip_tags(value).strip()

    def validate_bio(self, value):
        return strip_tags(value).strip()


class VehicleSerializer(serializers.ModelSerializer):
    # Dideklarasikan eksplisit supaya pelat dinormalisasi SEBELUM cek unique
    # ("b4567xyz" dan "B 4567 XYZ" dianggap pelat yang sama).
    plate_number = serializers.CharField(max_length=15)

    vehicle_type_display = serializers.SerializerMethodField()
    emission_category_display = serializers.SerializerMethodField()
    capacity_display = serializers.SerializerMethodField()
    is_low_emission = serializers.SerializerMethodField()

    class Meta:
        model = Vehicle
        fields = [
            "id", "vehicle_type", "vehicle_type_display", "name",
            "plate_number", "capacity", "capacity_display",
            "emission_category", "emission_category_display", "is_low_emission",
            "is_primary", "is_verified", "created_at", "updated_at",
        ]
        # owner tidak ada di fields: diisi server dari request.user.
        # is_verified hanya boleh diubah admin.
        read_only_fields = ["id", "is_verified", "created_at", "updated_at"]

    def get_vehicle_type_display(self, obj):
        return obj.get_vehicle_type_display()

    def get_emission_category_display(self, obj):
        return obj.get_emission_category_display()

    def get_capacity_display(self, obj):
        return obj.capacity_display

    def get_is_low_emission(self, obj):
        return obj.is_low_emission

    def validate_name(self, value):
        value = strip_tags(value).strip()
        if not value:
            raise serializers.ValidationError("Nama kendaraan tidak boleh kosong.")
        return value

    def validate_plate_number(self, value):
        plate = normalize_plate(value)
        try:
            check_plate_format(plate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)

        duplicates = Vehicle.objects.filter(plate_number=plate)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError("Pelat nomor ini sudah terdaftar.")
        return plate

    def validate(self, attrs):
        # Serializer tidak memanggil Vehicle.clean(), jadi aturan kapasitas dicek
        # di sini. Untuk PATCH, nilai yang tidak dikirim diambil dari instance lama.
        vehicle_type = attrs.get(
            "vehicle_type",
            getattr(self.instance, "vehicle_type", Vehicle.VehicleType.MOTOR),
        )
        capacity = attrs.get("capacity", getattr(self.instance, "capacity", 1))

        if capacity < 1:
            raise serializers.ValidationError(
                {"capacity": "Kapasitas minimal 1 kursi."}
            )
        max_capacity = Vehicle.MAX_CAPACITY.get(vehicle_type)
        if max_capacity and capacity > max_capacity:
            label = Vehicle.VehicleType(vehicle_type).label.lower()
            raise serializers.ValidationError(
                {"capacity": f"Kapasitas maksimal untuk {label} adalah {max_capacity} kursi."}
            )
        return attrs
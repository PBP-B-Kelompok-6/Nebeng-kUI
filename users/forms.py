from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from django import forms
from .models import Vehicle, normalize_plate

User = get_user_model()


class RegisterForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name", "npm")

class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = [
            "vehicle_type",
            "name",
            "plate_number",
            "capacity",
        ]
        labels = {
            "vehicle_type": "Jenis Kendaraan",
            "name": "Merek & Model",
            "plate_number": "Pelat Nomor",
            "capacity": "Kapasitas (kursi)",
        }

        def clean_plate_number(self):
                plate = normalize_plate(self.cleaned_data["plate_number"])
                qs = Vehicle.objects.filter(plate_number=plate)
                if self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                if qs.exists():
                    raise forms.ValidationError("Pelat nomor ini sudah terdaftar.")
                return plate
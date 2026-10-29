from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from django import forms
from .models import Vehicle, normalize_plate

User = get_user_model()
def validate_npm(value):
    value = value.strip()
    if value and not (value.isdigit() and len(value) == 10):
        raise forms.ValidationError("NPM harus 10 digit angka.")
    return value

FACULTIES = [
    "Fakultas Kedokteran",
    "Fakultas Kedokteran Gigi",
    "Fakultas Matematika dan Ilmu Pengetahuan Alam",
    "Fakultas Teknik",
    "Fakultas Hukum",
    "Fakultas Ekonomi dan Bisnis",
    "Fakultas Ilmu Pengetahuan Budaya",
    "Fakultas Psikologi",
    "Fakultas Ilmu Sosial dan Ilmu Politik",
    "Fakultas Kesehatan Masyarakat",
    "Fakultas Ilmu Komputer",
    "Fakultas Ilmu Keperawatan",
    "Fakultas Farmasi",
    "Fakultas Ilmu Administrasi",
    "Vokasi",
]
FACULTY_CHOICES = [("", "Pilih fakultas")] + [(f, f) for f in FACULTIES]

class ProfileForm(forms.ModelForm):
    faculty = forms.ChoiceField(
        choices=FACULTY_CHOICES, required=False, label="Fakultas"
    )

    class Meta:

        model = User
        fields = [
            "first_name", "last_name", "npm", "phone_number",
            "faculty", "bio", "profile_picture",
        ]
        labels = {
            "first_name": "Nama Depan",
            "last_name": "Nama Belakang",
            "npm": "NPM",
            "phone_number": "Nomor HP",
            "bio": "Bio",
            "profile_picture": "URL Foto Profil",
        }
        help_texts = {
            "profile_picture": "Tempel link gambar, contoh: https://...",
        }
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 4}),
        }
    def clean_npm(self):
        return validate_npm(self.cleaned_data["npm"])
    
class RegisterForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name", "npm")

    def clean_npm(self):
                return validate_npm(self.cleaned_data["npm"])
    
class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ["vehicle_type", "name", "plate_number", "capacity"]
        labels = {
            "vehicle_type": "Jenis Kendaraan",
            "name": "Merek & Model",
            "plate_number": "Pelat Nomor",
            "capacity": "Kapasitas (kursi)",
        }
        widgets = {
            "capacity": forms.NumberInput(attrs={"min": 1, "max": 8}),
        }

    def clean_plate_number(self):
        plate = normalize_plate(self.cleaned_data["plate_number"])
        qs = Vehicle.objects.filter(plate_number=plate)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Pelat nomor ini sudah terdaftar.")
        return plate

    def clean_capacity(self):
        capacity = self.cleaned_data["capacity"]
        if not 1 <= capacity <= 8:
            raise forms.ValidationError("Kapasitas harus antara 1 sampai 8 kursi.")
        return capacity
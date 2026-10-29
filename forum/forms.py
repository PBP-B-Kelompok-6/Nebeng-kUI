from django import forms
from .models import RidePost


class RidePostForm(forms.ModelForm):
    class Meta:
        model = RidePost
        fields = ["pickup_point", "destination", "departure_time", "max_quota", "notes"]
        labels = {
            "pickup_point": "Titik jemput",
            "destination": "Tujuan",
            "departure_time": "Waktu berangkat",
            "max_quota": "Jumlah kursi tersedia",
            "notes": "Catatan (opsional)",
        }
        widgets = {
            "pickup_point": forms.TextInput(attrs={"placeholder": "Contoh: Gerbang Kutek"}),
            "destination": forms.TextInput(attrs={"placeholder": "Contoh: Fakultas Teknik"}),
            "departure_time": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "max_quota": forms.NumberInput(attrs={"min": 1, "max": 6}),
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Motor/mobil, patokan, dll."}),
        }
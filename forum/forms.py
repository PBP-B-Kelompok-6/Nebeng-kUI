from django import forms
from .models import RidePost
from users.models import Vehicle

class RidePostForm(forms.ModelForm):
    class Meta:
        model = RidePost
        fields = ["kendaraan","pickup_point", "destination", "departure_time", "max_quota", "notes"]
        labels = {
            "kendaraan" : "Kendaraan",
            "pickup_point": "Titik jemput",
            "destination": "Tujuan",
            "departure_time": "Waktu berangkat",
            "max_quota": "Jumlah kursi tersedia",
            "notes": "Catatan (opsional)",
        }
        
        widgets = {
            "kendaraan": forms.Select(attrs={"class": "form-control"}),
            "pickup_point": forms.TextInput(attrs={"placeholder": "Contoh: Gerbang Kutek"}),
            "destination": forms.TextInput(attrs={"placeholder": "Contoh: Fakultas Teknik"}),
            "departure_time": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "max_quota": forms.NumberInput(attrs={"min": 1, "max": 6}),
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Motor/mobil, patokan, dll."}),
        }

    def __init__(self, *args, **kwargs):
            # Ambil user dari kwargs
                user = kwargs.pop('user', None)
                super().__init__(*args, **kwargs)
                
                # Filter pilihan kendaraan khusus untuk user yang sedang login
                if user:
                    self.fields['kendaraan'].queryset = Vehicle.objects.filter(owner=user)
                    # Tambahkan class CSS/placeholder jika perlu
                    self.fields['kendaraan'].widget.attrs.update({'class': 'form-control'})
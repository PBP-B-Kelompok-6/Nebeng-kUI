from django import forms
from .models import RidePost
from users.models import Vehicle
from maps.models import TitikKumpul

class RidePostForm(forms.ModelForm):
    class Meta:
        model = RidePost
        fields = ["kendaraan","pickup_point", "destination", "pickup_node", "destination_node", "departure_time", "notes"]
        labels = {
            "kendaraan" : "Kendaraan",
            "pickup_point": "Lokasi jemput",
            "destination": "Tujuan",
            "pickup_node" : "Titik jemput",
            "destination_node" : "Titik tujuan",
            "departure_time": "Waktu berangkat",
            "notes": "Catatan (opsional)",
        }
        
        widgets = {
            "kendaraan": forms.Select(attrs={"class": "form-control"}),
            "pickup_point": forms.TextInput(attrs={"placeholder": "Contoh: Gerbang Kutek"}),
            "destination": forms.TextInput(attrs={"placeholder": "Contoh: Fakultas Teknik"}),
            "pickup_node": forms.Select(attrs={"class": "form-control"}),
            "destination_node": forms.Select(attrs={"class": "form-control"}),
            "departure_time": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),

            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Motor/mobil, patokan, dll."}),
        }

    def __init__(self, *args, **kwargs):
            # Ambil user dari kwargs
                user = kwargs.pop('user', None)
                super().__init__(*args, **kwargs)

                self.fields['pickup_node'].queryset = TitikKumpul.objects.filter(aktif=True)
                self.fields['pickup_node'].empty_label = "-- Pilih Titik Jemput --"
                self.fields['destination_node'].queryset = TitikKumpul.objects.filter(aktif=True)
                self.fields['destination_node'].empty_label = "-- Pilih Titik Tujuan --"
                # Filter pilihan kendaraan khusus untuk user yang sedang login
                if user:
                    self.fields['kendaraan'].queryset = Vehicle.objects.filter(owner=user)
                    # Tambahkan class CSS/placeholder jika perlu
                    self.fields['kendaraan'].widget.attrs.update({'class': 'form-control'})
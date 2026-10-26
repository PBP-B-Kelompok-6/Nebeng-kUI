from django import forms
from .models import RidePost


class RidePostForm(forms.ModelForm):
    class Meta:
        model = RidePost
        fields = ["post_type", "pickup_point", "destination", "departure_time", "max_quota", "notes"]
        widgets = {
            "departure_time": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
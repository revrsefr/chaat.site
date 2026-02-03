from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .models import UserReport


class ReportUserForm(forms.ModelForm):
    reported_username = forms.CharField(label="User reported", max_length=150)

    class Meta:
        model = UserReport
        fields = ["reported_username", "motive"]
        labels = {
            "motive": "Motif",
        }
        widgets = {
            "motive": forms.Textarea(attrs={"rows": 6}),
        }

    def clean_reported_username(self):
        username = (self.cleaned_data.get("reported_username") or "").strip()
        if not username:
            raise ValidationError("Please provide a username.")

        user_model = get_user_model()
        reported = user_model.objects.filter(username__iexact=username).first()
        if reported is None:
            raise ValidationError("User not found.")

        self.reported_user = reported
        return username

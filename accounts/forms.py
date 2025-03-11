from django import forms
from .models import CustomUser

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ["username", "email", "password", "avatar", "gender", "city", "description", "age"]
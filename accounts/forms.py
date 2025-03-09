from django import forms
from django.contrib.auth.models import User
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Checkbox

class RegisterForm(forms.ModelForm):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)
    full_name = forms.CharField(max_length=255)
    birthday = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    gender = forms.ChoiceField(choices=[('male', 'Man'), ('female', 'Woman')])
    looking_for = forms.ChoiceField(choices=[('male', 'Man'), ('female', 'Woman')])
    marital_status = forms.ChoiceField(choices=[('single', 'Single'), ('married', 'Married')])
    city = forms.CharField(max_length=255)
    
    recaptcha = ReCaptchaField(widget=ReCaptchaV2Checkbox)  # Add Google reCAPTCHA

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'full_name', 'birthday', 'gender', 'looking_for', 'marital_status', 'city']

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords do not match.")

        return cleaned_data

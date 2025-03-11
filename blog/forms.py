from django import forms
from .models import Comment
from django_recaptcha.fields import ReCaptchaField

class CommentForm(forms.ModelForm):
    recaptcha = ReCaptchaField()
    
    class Meta:
        model = Comment
        fields = ["name", "email", "website", "content","recaptcha"]

from django.urls import path
from . import views

app_name = "recaptcha"

urlpatterns = [
    path("verify/", views.verify_session_token, name="verify_session_token"),
    path("process/", views.process_recaptcha, name="process_recaptcha"),
    path("check_token/", views.check_token, name="check_token"),
    path("check_trusted_token/", views.check_trusted_token, name="check_trusted_token"),
]
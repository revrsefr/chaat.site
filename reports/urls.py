from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("user/", views.report_user, name="report_user"),
]

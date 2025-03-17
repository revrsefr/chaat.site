from django.urls import path
from .views import webchat, dashboard

urlpatterns = [
    path('webchat/', webchat, name='webchat'),
    path("dashboard/", dashboard, name="irc_dashboard"),
]

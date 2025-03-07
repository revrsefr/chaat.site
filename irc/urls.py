from django.urls import path
from .views import webchat

urlpatterns = [
    path('webchat/', webchat, name='webchat'),  # This sets /irc/webchat/
]

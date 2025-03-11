from django.urls import path
from .views import community_membres

urlpatterns = [
    path("membres/", community_membres, name="community_membres"),
]
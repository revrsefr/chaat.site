from django.urls import path
from .views import community_membres, member_profile

urlpatterns = [
    path("membres/", community_membres, name="community_membres"),
    path("members/<str:username>/", member_profile, name="member_profile"), 
]
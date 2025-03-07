from django.urls import path
from .views import home

urlpatterns = [
    path('home/', home, name='home'),  # This sets /main/home/
]

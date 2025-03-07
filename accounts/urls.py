from django.urls import path
from .views import login_view, register_view  # Import at least one view

urlpatterns = [
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
]

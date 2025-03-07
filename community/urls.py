from django.urls import path
from .views import community  # Import the correct function

urlpatterns = [
    path('', community, name='community'),  # URL will be /community/
]

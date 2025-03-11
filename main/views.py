from django.shortcuts import render
from locations.models import City
from accounts.models import CustomUser

def home(request):
    members = CustomUser.objects.all()
    cities = City.objects.all().order_by("name")  # Sort alphabetically
    return render(request, 'main/home.html', {"members": members, "cities": cities})
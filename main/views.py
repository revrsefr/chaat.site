from django.shortcuts import render
from locations.models import City
from accounts.models import CustomUser
from django.http import HttpResponse
from django.template.loader import render_to_string
import requests


def home(request):
    members = CustomUser.objects.all()
    cities = City.objects.all().order_by("name")  # Sort alphabetically
    return render(request, 'main/home.html', {"members": members, "cities": cities})


def sitemap_xslt(request):
    xml = render_to_string('sitemap.xslt')
    return HttpResponse(xml, content_type='text/xml')
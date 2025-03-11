from django.http import JsonResponse
from locations.models import City

def get_cities(request):
    cities = list(City.objects.values_list("name", flat=True).order_by("name"))
    return JsonResponse({"cities": cities})
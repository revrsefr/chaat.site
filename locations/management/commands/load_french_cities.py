import requests
from django.core.management.base import BaseCommand
from locations.models import City
import time

GEONAMES_USERNAME = "reverse"  # ✅ Replace with your GeoNames username

class Command(BaseCommand):
    help = "Fetch and store all cities in France using GeoNames API"

    def handle(self, *args, **kwargs):
        url = f"http://api.geonames.org/searchJSON?country=FR&featureClass=P&maxRows=1000&username={GEONAMES_USERNAME}"
        response = requests.get(url)

        if response.status_code != 200:
            self.stderr.write(self.style.ERROR("❌ Failed to fetch cities from GeoNames API"))
            return

        data = response.json()
        cities = data.get("geonames", [])

        existing_cities = set(City.objects.values_list("name", flat=True))  # ✅ Get existing cities

        for city in cities:
            name = city["name"]
            latitude = city["lat"]
            longitude = city["lng"]

            if name in existing_cities:  # ✅ Skip duplicate cities
                self.stdout.write(self.style.WARNING(f"⚠️ {name} already exists, skipping."))
                continue

            City.objects.create(name=name, latitude=latitude, longitude=longitude)
            self.stdout.write(self.style.SUCCESS(f"✅ {name} added!"))

            time.sleep(1)  # ✅ Prevent API rate-limiting

        self.stdout.write(self.style.SUCCESS("✅ All cities added!"))

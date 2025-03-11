from django.db import models

class City(models.Model):
    name = models.CharField(max_length=255, null=True, unique=True)
    latitude = models.FloatField(null=True, blank=True)  # ✅ Ensure these fields exist
    longitude = models.FloatField(null=True, blank=True)

    def __str__(self):
        return self.name

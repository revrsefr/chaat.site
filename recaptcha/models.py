from django.db import models
from django.utils.timezone import now
from datetime import timedelta 

class VerificationToken(models.Model):
    token = models.CharField(max_length=255, unique=True) 
    created_at = models.DateTimeField(auto_now_add=True)
    expires_in = models.DurationField(default=timedelta(minutes=30))
    is_processed = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)  # Add this field

    def is_expired(self):
        return now() > self.created_at + self.expires_in
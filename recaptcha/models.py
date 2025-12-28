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


class TrustedIP(models.Model):
    """Stores a *keyed hash* of an IP address for short-lived trust.

    We store a hash (HMAC) rather than the raw IP to reduce sensitive data exposure.
    """

    ip_hash = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(default=now)
    expires_at = models.DateTimeField(db_index=True)

    def is_expired(self):
        return now() >= self.expires_at
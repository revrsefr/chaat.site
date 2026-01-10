from django.db import models
from django.utils import timezone


class LegalMentions(models.Model):
	singleton = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)

	publisher_name = models.CharField(max_length=255, blank=True)
	publisher_status = models.CharField(max_length=255, blank=True)
	publisher_address = models.TextField(blank=True)
	publisher_email = models.EmailField(blank=True)
	publisher_phone = models.CharField(max_length=64, blank=True)

	publisher_siren_siret = models.CharField(max_length=64, blank=True)
	publisher_rcs = models.CharField(max_length=255, blank=True)
	publisher_vat_number = models.CharField(max_length=64, blank=True)

	publication_director = models.CharField(max_length=255, blank=True)

	host_name = models.CharField(max_length=255, blank=True)
	host_address = models.TextField(blank=True)
	host_phone = models.CharField(max_length=64, blank=True)

	rgpd_controller = models.CharField(max_length=255, blank=True)
	rgpd_contact_email = models.EmailField(blank=True)
	retention_policy = models.TextField(blank=True)

	last_updated = models.DateField(default=timezone.localdate)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		verbose_name = "Mentions légales"
		verbose_name_plural = "Mentions légales"

	def save(self, *args, **kwargs):
		self.singleton = 1
		super().save(*args, **kwargs)

	@classmethod
	def get_solo(cls):
		obj, _ = cls.objects.get_or_create(singleton=1)
		return obj

	def __str__(self):
		return "Mentions légales"

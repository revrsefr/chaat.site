from django.contrib import admin

from .models import LegalMentions


@admin.register(LegalMentions)
class LegalMentionsAdmin(admin.ModelAdmin):
	fieldsets = (
		(
			"Éditeur",
			{
				"fields": (
					"publisher_name",
					"publisher_status",
					"publisher_address",
					"publisher_email",
					"publisher_phone",
					"publisher_siren_siret",
					"publisher_rcs",
					"publisher_vat_number",
				)
			},
		),
		("Publication", {"fields": ("publication_director",)}),
		(
			"Hébergeur",
			{
				"fields": (
					"host_name",
					"host_address",
					"host_phone",
				)
			},
		),
		(
			"RGPD",
			{
				"fields": (
					"rgpd_controller",
					"rgpd_contact_email",
					"retention_policy",
				)
			},
		),
		("Mise à jour", {"fields": ("last_updated",)}),
	)

	readonly_fields = ("created_at", "updated_at")
	list_display = ("__str__", "last_updated", "updated_at")

	def has_add_permission(self, request):
		if LegalMentions.objects.filter(singleton=1).exists():
			return False
		return super().has_add_permission(request)

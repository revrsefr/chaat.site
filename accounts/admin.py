import asyncio
import logging
from django.contrib import admin
from django.utils.html import format_html
from django.contrib.auth import get_user_model
from .authentication_async import get_nickserv_list  # ✅ Import the fixed function

logger = logging.getLogger(__name__)
User = get_user_model()

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ("username", "age", "gender", "online", "view_profile")
    search_fields = ("username",)
    list_filter = ("gender", "online")

    def get_queryset(self, request):
        """Override queryset to fetch users dynamically from Atheme."""
        try:
            authcookie = request.session.get("authcookie")
            username = request.session.get("atheme_user")

            if not authcookie:
                logger.warning("⚠️ Authcookie missing, retrying authentication...")
                return CustomUser.objects.none()

            user_queryset = asyncio.run(get_nickserv_list(authcookie, username))
            return user_queryset.all()  # ✅ Convert to Django-like QuerySet
        except Exception as e:
            logger.error(f"❌ Failed to fetch users from NickServ: {e}")
            return CustomUser.objects.none()

    def view_profile(self, obj):
        """Provide a link to the user's profile page."""
        return format_html('<a href="/admin/accounts/customuser/{}/change/">View</a>', obj.username)

    view_profile.short_description = "Profile"

    def has_delete_permission(self, request, obj=None):
        """Prevent accidental deletion of users from the admin panel."""
        return request.user.is_superuser  # Only superusers can delete

import logging
import asyncio
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
from asgiref.sync import async_to_sync
from .authentication_async import authenticate_atheme_async, get_nickserv_info

logger = logging.getLogger(__name__)
User = get_user_model()

# List of trusted IRC Admins who can access Django Admin
TRUSTED_ADMINS = {"reverse"}  # ✅ Replace with real IRC admins


class AthemeBackend(BaseBackend):
    """
    Custom authentication backend using Atheme JSON-RPC API.
    Ensures only specific users can access Django Admin.
    """

    def authenticate(self, request, username=None, password=None):
        """Django Admin calls this function - we must wrap async in sync"""
        if not username or not password:
            return None

        # Convert async function to sync
        authcookie = async_to_sync(authenticate_atheme_async)(username, password)
        if not authcookie:
            logger.warning(f"❌ Atheme authentication failed for user: {username}")
            return None

        return self.get_or_create_user(username, authcookie)

    def get_or_create_user(self, username, authcookie):
        """Fetch or create a user in Django while storing the Atheme authcookie."""
        user, created = User.objects.get_or_create(username=username)

        user.authcookie = authcookie
        user.is_active = True  # ✅ Ensure user is active

        # ✅ Only grant staff access to trusted admins
        if username in TRUSTED_ADMINS:
            user.is_staff = True  # ✅ Admin access to Django
            user.is_superuser = True  # ✅ Full admin privileges
            logger.info(f"✅ {username} granted Django Admin access.")
        else:
            user.is_staff = False
            user.is_superuser = False

        user.save()
        return user

    def get_user(self, user_id):
        """Retrieve user by ID."""
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

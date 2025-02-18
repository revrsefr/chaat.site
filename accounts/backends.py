import asyncio
import logging
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from .authentication_async import authenticate_atheme

logger = logging.getLogger(__name__)
User = get_user_model()

class AthemeBackend(BaseBackend):
    """
    Custom authentication backend using Atheme JSON-RPC API.
    """

    async def authenticate(self, request, username=None, password=None):
        """Authenticate a user with Atheme."""
        if not username or not password:
            return None

        authcookie = await authenticate_atheme(username, password)
        if not authcookie:
            logger.warning(f"❌ Atheme authentication failed for user: {username}")
            return None

        user, created = await self.get_or_create_user(username, authcookie)

        if created:
            logger.info(f"✅ New user created: {username}")

        # ✅ Store authcookie in database, so it's always available
        user.authcookie = authcookie
        await asyncio.to_thread(user.save)

        # ✅ Also store in session (if request exists)
        if request:
            request.session["authcookie"] = authcookie
            request.session["atheme_user"] = username
            request.session.modified = True

        return user

    async def get_or_create_user(self, username, authcookie):
        """Fetch or create a user in Django while storing the Atheme authcookie."""
        try:
            user = await asyncio.to_thread(User.objects.get, username=username)
            return user, False
        except User.DoesNotExist:
            user = User(username=username, authcookie=authcookie)
            await asyncio.to_thread(user.save)
            return user, True

    async def get_user(self, user_id):
        """Retrieve user by ID."""
        try:
            return await asyncio.to_thread(User.objects.get, pk=user_id)
        except User.DoesNotExist:
            return None

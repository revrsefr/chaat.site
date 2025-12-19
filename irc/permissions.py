import secrets
from typing import Optional

from django.conf import settings
from django.core import signing
from rest_framework.permissions import BasePermission


class IRCAPIAuthPermission(BasePermission):
    """Require either a privileged user or a shared API token header."""

    message = "Valid credentials required to access IRC telemetry."
    header_name = "X-Irc-Api-Token"
    signature_header = "X-Irc-Api-Signature"

    def _signer(self):
        key = getattr(settings, "IRC_API_TOKEN", None) or settings.SECRET_KEY
        return signing.TimestampSigner(key=key, salt="irc.api")

    def _signature_valid(self, provided: Optional[str]) -> bool:
        if not provided:
            return False
        max_age = getattr(settings, "IRC_API_SIGNATURE_MAX_AGE", 1800)
        try:
            self._signer().unsign(provided, max_age=max_age)
            return True
        except signing.BadSignature:
            return False

    def _token_valid(self, provided: Optional[str]) -> bool:
        expected = getattr(settings, "IRC_API_TOKEN", None)
        if not expected or not provided:
            return False
        try:
            return secrets.compare_digest(provided.strip(), expected)
        except Exception:
            return False

    def has_permission(self, request, view):
        header_token = request.headers.get(self.header_name)
        if self._token_valid(header_token):
            return True

        signature_token = request.headers.get(self.signature_header)
        if self._signature_valid(signature_token):
            return True

        user = getattr(request, "user", None)
        if user and user.is_authenticated and (user.is_staff or user.is_superuser):
            return True

        return False

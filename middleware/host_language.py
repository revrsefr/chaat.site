from __future__ import annotations

from django.conf import settings
from django.utils import translation


class HostLanguageMiddleware:
    """Force language by host when no language is explicitly set."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = (request.get_host() or "").split(":", 1)[0].lower()
        forced_language = self._get_forced_language(request, host)
        if forced_language:
            translation.activate(forced_language)
            request.LANGUAGE_CODE = forced_language

        response = self.get_response(request)

        if forced_language:
            response.set_cookie(
                settings.LANGUAGE_COOKIE_NAME,
            forced_language,
                max_age=getattr(settings, "LANGUAGE_COOKIE_AGE", None),
                path=getattr(settings, "LANGUAGE_COOKIE_PATH", "/"),
                domain=getattr(settings, "LANGUAGE_COOKIE_DOMAIN", None),
                secure=getattr(settings, "LANGUAGE_COOKIE_SECURE", None),
                httponly=getattr(settings, "LANGUAGE_COOKIE_HTTPONLY", False),
                samesite=getattr(settings, "LANGUAGE_COOKIE_SAMESITE", None),
            )

        return response

    def _get_forced_language(self, request, host: str) -> str | None:
        if settings.LANGUAGE_COOKIE_NAME in request.COOKIES:
            return None

        if host in {"puntochat.net", "www.puntochat.net"}:
            return "es"

        if host in {"chaat.site", "www.chaat.site"}:
            return "fr"

        return None

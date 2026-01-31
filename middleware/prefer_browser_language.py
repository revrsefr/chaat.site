from django.conf import settings
from django.utils.deprecation import MiddlewareMixin


class PreferBrowserLanguageMiddleware(MiddlewareMixin):
    """Prefer Accept-Language over an existing language cookie.

    If the browser sends Accept-Language and the language cookie is set,
    drop the cookie so LocaleMiddleware resolves from the header.
    """

    def process_request(self, request):
        accept_language = request.META.get("HTTP_ACCEPT_LANGUAGE")
        if not accept_language:
            return None

        language_cookie = settings.LANGUAGE_COOKIE_NAME
        if language_cookie in request.COOKIES:
            request.COOKIES.pop(language_cookie, None)

        return None

from __future__ import annotations


class InternalApiHttpsMiddleware:
    """Mark specific *local* internal API requests as "secure".

    In production we enable `SECURE_SSL_REDIRECT`, which is correct for browser
    traffic behind a TLS-terminating reverse proxy. However, some internal
    services (e.g. Anope modules) call Daphne directly over loopback HTTP.

    If Django sees those requests as non-secure, `SecurityMiddleware` will issue
    a 301/302 redirect to HTTPS, which breaks clients that expect HTTP 200.

    We only override the scheme for the exact internal endpoint and only when
    the request originates from loopback.
    """

    INTERNAL_HTTPS_PATH_PREFIXES = (
        "/accounts/api/login_token/",
    )

    LOOPBACK_IPS = {"127.0.0.1", "::1"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            remote_addr = request.META.get("REMOTE_ADDR")
            if (
                remote_addr in self.LOOPBACK_IPS
                and request.path.startswith(self.INTERNAL_HTTPS_PATH_PREFIXES)
                and not request.META.get("HTTP_X_FORWARDED_PROTO")
            ):
                # Make request.is_secure() return True.
                request.META["HTTP_X_FORWARDED_PROTO"] = "https"
                request.META["wsgi.url_scheme"] = "https"
        except Exception:
            # Never block requests due to scheme override.
            pass

        return self.get_response(request)

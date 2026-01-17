from __future__ import annotations

from urllib.parse import urlsplit

from django import template

register = template.Library()

_ALLOWED_SCHEMES = {"http", "https", "mailto", "tel"}


@register.filter(name="safe_url")
def safe_url(value: object) -> str:
    """Return a URL safe for use in href/src attributes.

    Blocks dangerous schemes like javascript: and protocol-relative URLs (//host).
    Allows relative URLs and http(s)/mailto/tel.
    """

    if value is None:
        return "#"

    url = str(value).strip()
    if not url:
        return "#"

    parts = urlsplit(url)

    if parts.scheme:
        return url if parts.scheme.lower() in _ALLOWED_SCHEMES else "#"

    if parts.netloc:
        return "#"

    return url

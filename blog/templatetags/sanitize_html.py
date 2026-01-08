from __future__ import annotations

from django import template
from django.utils.safestring import mark_safe

import bleach

register = template.Library()

# Allow a small, blog-friendly subset of HTML.
_ALLOWED_TAGS = {
    "p",
    "br",
    "hr",
    "blockquote",
    "pre",
    "code",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "ul",
    "ol",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "a",
}

_ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "target", "rel"],
}

_ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


@register.filter(name="sanitize_html")
def sanitize_html(value: str | None) -> str:
    if not value:
        return ""

    cleaned = bleach.clean(
        value,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        protocols=_ALLOWED_PROTOCOLS,
        strip=True,
    )

    # Convert plain URLs into links (safe after `bleach.clean`).
    cleaned = bleach.linkify(
        cleaned,
        callbacks=[bleach.callbacks.nofollow, bleach.callbacks.target_blank],
        skip_tags=["pre", "code"],
    )

    return mark_safe(cleaned)

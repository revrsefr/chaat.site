import hashlib

from django import template

register = template.Library()


@register.filter(name="gravatar_hash")
def gravatar_hash(email: str | None) -> str:
    if not email:
        return ""
    normalized = email.strip().lower().encode("utf-8")
    return hashlib.md5(normalized).hexdigest()

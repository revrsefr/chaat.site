from __future__ import annotations

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def qs(context, **kwargs) -> str:
    """Return the current querystring updated with the given key/value pairs.

    Usage:
        href="?{% qs page=2 %}"

    Pass `None` to remove a key:
        {% qs page=None %}
    """
    request = context.get("request")
    if request is None:
        return ""

    query = request.GET.copy()
    for key, value in kwargs.items():
        if value is None or value == "":
            query.pop(key, None)
        else:
            query[key] = str(value)
    return query.urlencode()

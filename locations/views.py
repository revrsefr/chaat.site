import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from locations.models import City


def _ban_municipality_suggestions(query: str, limit: int) -> list[str]:
    """Return municipality (city) suggestions using the BAN API.

    Works well for postal codes and city name fragments.
    """

    base_url = "https://api-adresse.data.gouv.fr/search/"
    params = {
        "q": query,
        "type": "municipality",
        "limit": limit,
    }
    url = f"{base_url}?{urlencode(params)}"
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "chaat.site"})
    with urlopen(req, timeout=4) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    features = payload.get("features") or []
    seen: set[str] = set()
    results: list[str] = []

    for feature in features:
        props = feature.get("properties") or {}
        city = (props.get("city") or props.get("name") or "").strip()
        if not city:
            continue
        if city in seen:
            continue
        seen.add(city)
        results.append(city)
        if len(results) >= limit:
            break

    return results


@require_GET
def get_cities(request):
    """Return French city names for autocomplete.

    Query params:
    - q: search prefix (required; min 2 chars)
    - limit: max results (default 25, max 100)
    """

    query = (request.GET.get("q") or "").strip()
    try:
        limit = int(request.GET.get("limit") or 25)
    except (TypeError, ValueError):
        limit = 25
    limit = max(1, min(limit, 100))

    if len(query) < 2:
        return JsonResponse({"cities": []})

    # If the user types a postal code (or prefix), use BAN to suggest matching cities.
    if query.isdigit():
        try:
            return JsonResponse({"cities": _ban_municipality_suggestions(query, limit)})
        except Exception:
            # Fail closed: don't break the homepage form if external API is down.
            return JsonResponse({"cities": []})

    cities = (
        City.objects.filter(name__istartswith=query)
        .order_by("name")
        .values_list("name", flat=True)[:limit]
    )
    return JsonResponse({"cities": list(cities)})
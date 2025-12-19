from __future__ import annotations

from typing import Dict

from django.conf import settings


def _normalize_host(host: str) -> str:
    """Return a lower-cased hostname without the port information."""

    if not host:
        return ""
    return host.split(":", maxsplit=1)[0].lower()


def _brand_for_host(host: str) -> Dict[str, str]:
    """Fetch the configured brand entry or fall back to the hostname itself."""

    site_brands = getattr(settings, "SITE_BRANDS", {})
    if host in site_brands:
        return site_brands[host]

    if host.startswith("www."):
        bare_host = host[4:]
        if bare_host in site_brands:
            base_brand = site_brands[bare_host].copy()
            base_brand.update(
                {
                    "host": host,
                    "site_name": host,
                    "title_suffix": host,
                    "meta_author": host,
                }
            )
            return base_brand

    fallback_value = host or "localhost"
    return {
        "host": fallback_value,
        "site_name": fallback_value,
        "title_suffix": fallback_value,
        "meta_author": fallback_value,
    }


def site_branding(request):
    """Expose host-aware site metadata and a canonical URL to all templates."""

    normalized_host = _normalize_host(request.get_host() if request else "")
    brand_config = _brand_for_host(normalized_host)
    brand = brand_config.copy()

    fallback_host = (
        normalized_host
        or getattr(settings, "DEFAULT_DOMAIN", "")
        or (settings.ALLOWED_HOSTS[0] if getattr(settings, "ALLOWED_HOSTS", None) else "localhost")
    )
    host_value = brand.get("host") or fallback_host

    if request:
        forwarded_proto = request.META.get("HTTP_X_FORWARDED_PROTO", "")
        if forwarded_proto:
            scheme = forwarded_proto.split(",", maxsplit=1)[0]
        else:
            scheme = "https" if request.is_secure() else request.scheme
    else:
        scheme = "https"

    base_url = brand.get("base_url") or f"{scheme}://{host_value}"
    site_name = brand.get("site_name") or host_value

    brand.update(
        {
            "host": host_value,
            "domain": host_value,
            "site_name": site_name,
            "title_suffix": brand.get("title_suffix") or host_value,
            "meta_author": brand.get("meta_author") or site_name,
            "base_url": base_url.rstrip("/"),
        }
    )

    brand.setdefault("default_title", f"home - {brand['title_suffix']}")

    path = request.path if request else "/"
    canonical_url = f"{brand['base_url']}{path}"

    return {
        "site_brand": brand,
        "canonical_url": canonical_url,
    }

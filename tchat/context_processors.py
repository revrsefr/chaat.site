from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict

from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import NoReverseMatch, reverse


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
            "logo_url": brand.get("logo_url") or "images/logo/mark-2026-v4.svg",
        }
    )

    brand.setdefault("default_title", f"home - {brand['title_suffix']}")

    path = request.path if request else "/"
    canonical_url = f"{brand['base_url']}{path}"

    return {
        "site_brand": brand,
        "canonical_url": canonical_url,
        "static_version": getattr(settings, "STATIC_VERSION", "") or "1",
        "cmp_enabled": bool(getattr(settings, "ENABLE_TCF_CMP", False)),
        "google_fc_publisher_id": getattr(settings, "GOOGLE_FC_PUBLISHER_ID", None),
    }


def _footer_for_host(host: str) -> dict:
    site_footers = getattr(settings, "SITE_FOOTERS", {})
    if host in site_footers:
        return site_footers[host]

    if host.startswith("www."):
        bare_host = host[4:]
        if bare_host in site_footers:
            return site_footers[bare_host]

    return getattr(settings, "DEFAULT_SITE_FOOTER", {})


def _safe_reverse(viewname: str, *args, **kwargs) -> str:
    try:
        return reverse(viewname, args=args, kwargs=kwargs)
    except NoReverseMatch:
        return "#"


def _sanitize_footer_links(items: object) -> list:
    """Best-effort sanitize a list of link dicts.

    This protects against dangerous schemes (e.g. javascript:) in any configured
    footer links. It's defensive: it never raises.
    """

    if not isinstance(items, (list, tuple)):
        return []

    try:
        from main.templatetags.safe_url import safe_url as _safe_url
    except Exception:
        _safe_url = None

    sanitized: list = []
    for item in items:
        if not isinstance(item, dict):
            continue
        url_value = item.get("url")
        if _safe_url is not None:
            item = item.copy()
            item["url"] = _safe_url(url_value)
        sanitized.append(item)

    return sanitized


def site_footer(request):
    """Expose footer configuration + latest users to all templates.

    This is intentionally defensive: it should never break template rendering
    (e.g. during maintenance, migrations, or partial deployments).
    """

    normalized_host = _normalize_host(request.get_host() if request else "")
    configured = _footer_for_host(normalized_host) or {}

    footer = {
        "background_image": configured.get("background_image", "images/footer/bg-2.jpg"),
        "tagline": configured.get(
            "tagline",
            "Chat gratuit, sans inscription — discutez et rencontrez du monde.",
        ),
        "help_channel": configured.get("help_channel", "#aide"),
        "help_text": configured.get(
            "help_text",
            "Nos opérateurs seront ravis de vous aider.",
        ),
        "legal_links": _sanitize_footer_links(
            configured.get(
            "legal_links",
            [
                {"label": "Conditions générales", "url": _safe_reverse("main:terms")},
                {"label": "Mentions légales", "url": _safe_reverse("main:legal")},
                {"label": "À propos", "url": _safe_reverse("main:about")},
            ],
            )
        ),
        "information_links": _sanitize_footer_links(
            configured.get(
            "information_links",
            [
                {"label": "Network", "url": _safe_reverse("irc_dashboard")},
            ],
            )
        ),
        "useful_links": _sanitize_footer_links(
            configured.get(
            "useful_links",
            [
                {"label": "Membres", "url": _safe_reverse("community_membres")},
                {"label": "Blog", "url": _safe_reverse("blog:blog_list")},
                {"label": "Inscription", "url": _safe_reverse("register")},
                {"label": "Connexion", "url": _safe_reverse("login")},
            ],
            )
        ),
        "social_links": _sanitize_footer_links(configured.get("social_links", [])),
        "year": datetime.now().year,
        "recent_articles": [],
        "latest_users": [],
    }

    recent_articles_count = int(configured.get("recent_articles_count", 3) or 3)
    if recent_articles_count > 0:
        try:
            from blog.models import BlogPost

            recent_posts = (
                BlogPost.objects.filter(is_active=True, is_published=True)
                .only("title", "slug", "created_at")
                .order_by("-created_at")[:recent_articles_count]
            )
            footer["recent_articles"] = [
                {"title": post.title, "url": _safe_reverse("blog:blog_detail", slug=post.slug)}
                for post in recent_posts
            ]
        except Exception:
            footer["recent_articles"] = []

    latest_users_count = int(configured.get("latest_users_count", 5) or 5)
    if latest_users_count > 0:
        try:
            User = get_user_model()
            footer["latest_users"] = list(
                User.objects.only("username", "date_joined", "avatar").order_by("-date_joined")[:latest_users_count]
            )
        except Exception:
            footer["latest_users"] = []

    return {"footer": footer}

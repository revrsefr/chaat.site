from __future__ import annotations

from django.conf import settings
import django_rq

from .services import AnopeStatsService


def refresh_network_overview_cache() -> dict:
    service = AnopeStatsService()
    return service.refresh_network_overview_cache(ttl=settings.IRC_STATS_CACHE_TTL)


def enqueue_refresh_network_overview_cache() -> str:
    queue = django_rq.get_queue("default")
    job = queue.enqueue(refresh_network_overview_cache)
    return job.id

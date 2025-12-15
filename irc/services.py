import logging
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .rpc_client import AnopeRPC, RPCError


logger = logging.getLogger(__name__)


class AnopeStatsService:
    """Cached helper around the Anope JSON-RPC surface."""

    def __init__(
        self,
        rpc: Optional[AnopeRPC] = None,
        cache_prefix: str = "irc.stats",
        default_ttl: int = 20,
    ) -> None:
        self.rpc = rpc or AnopeRPC(token=getattr(settings, "ANOPE_RPC_TOKEN", None))
        self.cache_prefix = cache_prefix
        self.default_ttl = default_ttl

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _cache_key(self, suffix: str) -> str:
        return f"{self.cache_prefix}.{suffix}"

    def _cached(self, key: str, producer, ttl: Optional[int] = None):
        cache_key = self._cache_key(key)
        payload = cache.get(cache_key)
        if payload is None:
            payload = producer()
            cache.set(cache_key, payload, ttl or self.default_ttl)
        return payload

    # ------------------------------------------------------------------
    # Normalizers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_secret_channel(modes: Any) -> bool:
        if not modes:
            return False
        if isinstance(modes, str):
            modes = [modes]
        if not isinstance(modes, list):
            return False

        for mode in modes:
            token = str(mode).strip().lower()
            if token == "secret":
                return True
            if token.startswith("+"):
                # Flag modes are usually grouped like "+nt".
                flags = token[1:].split()[0] if token[1:] else ""
                if "s" in flags:
                    return True
        return False

    def _normalize_channels(self, raw: Any) -> List[Dict[str, Any]]:
        channels: List[Dict[str, Any]] = []
        if isinstance(raw, dict):
            iterable = raw.items()
        elif isinstance(raw, list):
            iterable = ((name, {}) for name in raw)
        else:
            iterable = []

        for name, data in iterable:
            entry = dict(data or {})
            entry.setdefault("name", name)
            users = entry.get("users") or []
            entry["user_count"] = len(users)

            modes = entry.get("modes") or []
            if isinstance(modes, str):
                modes = [modes]
            if not isinstance(modes, list):
                modes = []
            entry["modes"] = modes
            entry["modes_display"] = " ".join(str(mode) for mode in modes) or None
            entry["is_secret"] = self._is_secret_channel(modes)

            topic = entry.get("topic") or {}
            entry["topic_value"] = topic.get("value")
            channels.append(entry)

        channels.sort(key=lambda c: c.get("user_count", 0), reverse=True)
        return channels

    def _normalize_servers(self, raw: Any) -> List[Dict[str, Any]]:
        servers: List[Dict[str, Any]] = []
        if isinstance(raw, dict):
            iterable = raw.items()
        elif isinstance(raw, list):
            iterable = ((name, {}) for name in raw)
        else:
            iterable = []

        for name, data in iterable:
            entry = dict(data or {})
            entry.setdefault("name", name)
            entry["downlink_count"] = len(entry.get("downlinks") or [])
            servers.append(entry)

        servers.sort(key=lambda srv: (not srv.get("synced", False), srv.get("name", "")))
        return servers

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def network_overview(self) -> Dict[str, Any]:
        def fetch():
            channels = self.rpc.list_channels("name") or []
            users = self.rpc.list_users("name") or []
            servers = self.rpc.list_servers("name") or []
            operators = self.rpc.list_opers("name") or []
            return {
                "counts": {
                    "channels": len(channels),
                    "users": len(users),
                    "servers": len(servers),
                    "operators": len(operators),
                },
                "updated_at": timezone.now().isoformat(),
            }

        return self._cached("network.overview", fetch, ttl=10)

    def channel_listing(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        def fetch():
            raw = self.rpc.list_channels("full")
            return self._normalize_channels(raw)

        entries = [entry for entry in self._cached("channels.full", fetch, ttl=30) if not entry.get("is_secret")]
        if limit is not None:
            return entries[:limit]
        return list(entries)

    def channel_detail(self, name: str) -> Optional[Dict[str, Any]]:
        cache_key = self._cache_key(f"channel.{name}")
        payload = cache.get(cache_key)
        if payload is None:
            payload = self.rpc.channel(name)
            cache.set(cache_key, payload, self.default_ttl)
        return payload

    def server_listing(self) -> List[Dict[str, Any]]:
        def fetch():
            raw = self.rpc.list_servers("full")
            return self._normalize_servers(raw)

        return list(self._cached("servers.full", fetch, ttl=30))

    def server_detail(self, name: str) -> Optional[Dict[str, Any]]:
        cache_key = self._cache_key(f"server.{name}")
        payload = cache.get(cache_key)
        if payload is None:
            payload = self.rpc.server(name)
            cache.set(cache_key, payload, self.default_ttl)
        return payload

    def user_listing(self, limit: int = 50) -> List[str]:
        def fetch():
            names = self.rpc.list_users("name") or []
            return sorted(names)

        users = self._cached("users.names", fetch, ttl=10)
        return users[:limit]

    def user_detail(self, nickname: str) -> Optional[Dict[str, Any]]:
        cache_key = self._cache_key(f"user.{nickname}")
        payload = cache.get(cache_key)
        if payload is None:
            payload = self.rpc.user(nickname)
            cache.set(cache_key, payload, self.default_ttl)
        return payload

    def operator_listing(self) -> List[Dict[str, Any]]:
        def fetch():
            data = self.rpc.list_opers("full")
            if isinstance(data, dict):
                return [dict(entry or {}, name=name) for name, entry in data.items()]
            return []

        return list(self._cached("opers.full", fetch, ttl=60))

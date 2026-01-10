import logging
import secrets
import re
from datetime import timedelta
from functools import cached_property

from django.conf import settings
from django.core import signing
from django.shortcuts import render
from django.utils import timezone
from django.urls import reverse
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import TelemetrySnapshot
from .permissions import IRCAPIAuthPermission
from .rpc_client import RPCError
from .services import AnopeStatsService


logger = logging.getLogger(__name__)


_CHANSTATS_PERIODS = {"total", "monthly", "weekly", "daily"}
_CHANSTATS_METRICS = {
    "letters",
    "words",
    "lines",
    "actions",
    "smileys_happy",
    "smileys_sad",
    "smileys_other",
    "kicks",
    "kicked",
    "modes",
    "topics",
}


def _parse_chanstats_query_params(request):
    period = (request.query_params.get("period") or "daily").strip().lower()
    if period not in _CHANSTATS_PERIODS:
        raise ValidationError(detail="Invalid period (expected total/monthly/weekly/daily)")

    metric = (request.query_params.get("metric") or "lines").strip().lower()
    if metric not in _CHANSTATS_METRICS:
        raise ValidationError(detail="Invalid metric")

    limit_raw = request.query_params.get("limit") or "10"
    try:
        limit = int(limit_raw)
    except ValueError:
        limit = 10
    limit = min(max(limit, 1), 100)

    period_start = (request.query_params.get("period_start") or "").strip()
    if period_start and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", period_start):
        raise ValidationError(detail="Invalid period_start (expected YYYY-MM-DD)")

    return {
        "period": period,
        "metric": metric,
        "limit": limit,
        "period_start": period_start or None,
    }


def webchat(request):
    return render(request, 'irc/webchat.html')


def _mint_api_signature():
    key = getattr(settings, "IRC_API_TOKEN", None) or settings.SECRET_KEY
    signer = signing.TimestampSigner(key=key, salt="irc.api")
    return signer.sign(secrets.token_urlsafe(16))


def dashboard(request):
    """Render the interactive MagIRC-inspired dashboard."""

    service = AnopeStatsService()
    initial_payload = {}
    try:
        initial_payload["overview"] = service.network_overview()
        initial_payload["channels"] = service.channel_listing(limit=8)
        initial_payload["servers"] = service.server_listing()[:4]
        initial_payload["users"] = service.user_listing(limit=25)
        initial_payload["operators"] = service.operator_listing()

        # chanstats_plus highlights
        initial_payload["chanstats_top_channels"] = service.chanstatsplus_top_channels()
        initial_payload["chanstats_top_nicks_global"] = service.chanstatsplus_top_nicks_global()

        seed_channel = None
        for entry in initial_payload.get("channels") or []:
            name = (entry or {}).get("name")
            if name:
                seed_channel = name
                break
        initial_payload["chanstats_seed_channel"] = seed_channel
        if seed_channel:
            initial_payload["chanstats_top_in_channel"] = service.chanstatsplus_top_in_channel(seed_channel)

        # DB-backed history (if snapshot collection is enabled).
        since = timezone.now() - timedelta(hours=72)
        history_qs = TelemetrySnapshot.objects.filter(recorded_at__gte=since).order_by("-recorded_at")[:200]
        history_points = [
            {
                "recorded_at": snap.recorded_at.isoformat(),
                "users": snap.user_count,
                "channels": snap.channel_count,
                "servers": snap.server_count,
                "operators": snap.operator_count,
            }
            for snap in reversed(list(history_qs))
        ]

        def _max_row(field: str):
            row = (
                TelemetrySnapshot.objects.order_by(f"-{field}", "-recorded_at")
                .values(field, "recorded_at")
                .first()
            )
            if not row:
                return None
            return {"value": row.get(field, 0), "recorded_at": row["recorded_at"].isoformat()}

        initial_payload["history"] = {
            "range": {"hours": 72, "limit": 200},
            "points": history_points,
            "max": {
                "users": _max_row("user_count"),
                "channels": _max_row("channel_count"),
                "servers": _max_row("server_count"),
                "operators": _max_row("operator_count"),
            },
        }
    except RPCError as exc:
        logger.warning("Anope RPC unavailable during dashboard seed: %s", exc)
        initial_payload["error"] = "The IRC telemetry endpoint is temporarily unavailable."

    api_endpoints = {
        "overview": reverse("irc_api_network_overview"),
        "history": reverse("irc_api_history"),
        "channels": reverse("irc_api_channels"),
        "servers": reverse("irc_api_servers"),
        "users": reverse("irc_api_users"),
        "user_detail_template": reverse(
            "irc_api_user_detail",
            kwargs={"nickname": "__NICK__"},
        ),
        "operators": reverse("irc_api_operators"),

        # chanstats_plus
        "chanstats_top_channels": reverse("irc_api_chanstatsplus_top_channels"),
        "chanstats_top_nicks_global": reverse("irc_api_chanstatsplus_top_nicks_global"),
        "chanstats_top_in_channel_template": reverse(
            "irc_api_chanstatsplus_top_in_channel",
            kwargs={"channel_name": "__CHAN__"},
        ),
    }

    return render(
        request,
        "irc/dashboard.html",
        {
            "initial_payload": initial_payload,
            "api_endpoints": api_endpoints,
            "api_signature": _mint_api_signature(),
        },
    )


class UpstreamUnavailable(APIException):
    status_code = 502
    default_detail = "Anope RPC is currently unavailable."


class AnopeAPIView(APIView):
    """Shared plumbing for JSON views backed by the Anope RPC."""

    service_class = AnopeStatsService
    not_found_markers = {"-32099", "-32098"}
    permission_classes = (IRCAPIAuthPermission,)
    throttle_scope = "irc_api"

    @cached_property
    def service(self):
        return self.service_class()

    def _raise_unavailable(self, exc: RPCError):
        logger.warning("Anope RPC failure in %s: %s", self.__class__.__name__, exc)
        raise UpstreamUnavailable() from exc

    def _is_not_found(self, exc: RPCError) -> bool:
        text = str(exc)
        return any(marker in text for marker in self.not_found_markers)


class NetworkOverviewView(AnopeAPIView):
    def get(self, request):
        try:
            payload = self.service.network_overview()
        except RPCError as exc:
            self._raise_unavailable(exc)
        return Response(payload)


class TelemetryHistoryView(APIView):
    """Serves DB-collected history for charts (independent of live RPC)."""

    permission_classes = (IRCAPIAuthPermission,)
    throttle_scope = "irc_api"

    def get(self, request):
        hours_raw = (request.query_params.get("hours") or "72").strip()
        limit_raw = (request.query_params.get("limit") or "200").strip()
        try:
            hours = int(hours_raw)
        except ValueError:
            hours = 72
        try:
            limit = int(limit_raw)
        except ValueError:
            limit = 200

        hours = min(max(hours, 1), 24 * 30)
        limit = min(max(limit, 10), 2000)

        since = timezone.now() - timedelta(hours=hours)
        qs = TelemetrySnapshot.objects.filter(recorded_at__gte=since).order_by("-recorded_at")[:limit]
        points = [
            {
                "recorded_at": snap.recorded_at.isoformat(),
                "users": snap.user_count,
                "channels": snap.channel_count,
                "servers": snap.server_count,
                "operators": snap.operator_count,
            }
            for snap in reversed(list(qs))
        ]

        def _max_row(field: str):
            row = (
                TelemetrySnapshot.objects.order_by(f"-{field}", "-recorded_at")
                .values(field, "recorded_at")
                .first()
            )
            if not row:
                return None
            return {"value": row.get(field, 0), "recorded_at": row["recorded_at"].isoformat()}

        return Response(
            {
                "range": {"hours": hours, "limit": limit},
                "points": points,
                "max": {
                    "users": _max_row("user_count"),
                    "channels": _max_row("channel_count"),
                    "servers": _max_row("server_count"),
                    "operators": _max_row("operator_count"),
                },
            }
        )


class ChannelListView(AnopeAPIView):
    def get(self, request):
        query = request.query_params.get("q", "").strip().lower()
        limit_param = request.query_params.get("limit")
        try:
            limit = min(max(int(limit_param), 1), 500) if limit_param else None
        except ValueError:
            limit = None

        try:
            channels = self.service.channel_listing()
        except RPCError as exc:
            self._raise_unavailable(exc)

        channels = [entry for entry in channels if not entry.get("is_secret")]

        if query:
            channels = [
                entry
                for entry in channels
                if query in entry.get("name", "").lower()
                or query in (entry.get("topic_value") or "").lower()
                or query in (entry.get("modes_display") or "").lower()
            ]

        if limit is not None:
            channels = channels[:limit]

        return Response({"count": len(channels), "results": channels})


class ChannelDetailView(AnopeAPIView):
    def get(self, request, channel_name):
        try:
            payload = self.service.channel_detail(channel_name)
        except RPCError as exc:
            if self._is_not_found(exc):
                raise NotFound(detail="Channel not found.") from exc
            self._raise_unavailable(exc)

        if not payload:
            raise NotFound(detail="Channel not found.")

        payload.setdefault("user_count", len(payload.get("users", [])))
        modes = payload.get("modes") or []
        if isinstance(modes, str):
            modes = [modes]
        if not isinstance(modes, list):
            modes = []
        payload.setdefault("modes", modes)
        payload.setdefault("modes_display", " ".join(str(mode) for mode in modes) or None)
        return Response(payload)


class ServerListView(AnopeAPIView):
    def get(self, request):
        try:
            servers = self.service.server_listing()
        except RPCError as exc:
            self._raise_unavailable(exc)
        return Response({"count": len(servers), "results": servers})


class ServerDetailView(AnopeAPIView):
    def get(self, request, server_name):
        try:
            payload = self.service.server_detail(server_name)
        except RPCError as exc:
            if self._is_not_found(exc):
                raise NotFound(detail="Server not found.") from exc
            self._raise_unavailable(exc)

        if not payload:
            raise NotFound(detail="Server not found.")
        return Response(payload)


class UserListView(AnopeAPIView):
    def get(self, request):
        query = request.query_params.get("q", "").strip().lower()
        limit_param = request.query_params.get("limit")
        try:
            limit = min(max(int(limit_param), 1), 500) if limit_param else 50
        except ValueError:
            limit = 50

        try:
            users = self.service.user_listing(limit=500)
        except RPCError as exc:
            self._raise_unavailable(exc)

        if query:
            users = [name for name in users if query in name.lower()]

        return Response({"count": len(users[:limit]), "results": users[:limit]})


class UserDetailView(AnopeAPIView):
    def get(self, request, nickname):
        try:
            payload = self.service.user_detail(nickname)
        except RPCError as exc:
            if self._is_not_found(exc):
                raise NotFound(detail="User not found.") from exc
            self._raise_unavailable(exc)

        if not payload:
            raise NotFound(detail="User not found.")
        return Response(payload)


class OperatorListView(AnopeAPIView):
    def get(self, request):
        try:
            opers = self.service.operator_listing()
        except RPCError as exc:
            self._raise_unavailable(exc)
        return Response({"count": len(opers), "results": opers})


class ChanstatsPlusTopChannelsView(AnopeAPIView):
    def get(self, request):
        params = _parse_chanstats_query_params(request)
        try:
            results = self.service.chanstatsplus_top_channels(
                period=params["period"],
                metric=params["metric"],
                limit=params["limit"],
                period_start=params["period_start"],
            )
        except RPCError as exc:
            self._raise_unavailable(exc)
        return Response({"count": len(results), "results": results, **params})


class ChanstatsPlusTopNicksGlobalView(AnopeAPIView):
    def get(self, request):
        params = _parse_chanstats_query_params(request)
        try:
            results = self.service.chanstatsplus_top_nicks_global(
                period=params["period"],
                metric=params["metric"],
                limit=params["limit"],
                period_start=params["period_start"],
            )
        except RPCError as exc:
            self._raise_unavailable(exc)
        return Response({"count": len(results), "results": results, **params})


class ChanstatsPlusTopInChannelView(AnopeAPIView):
    def get(self, request, channel_name):
        params = _parse_chanstats_query_params(request)
        try:
            results = self.service.chanstatsplus_top_in_channel(
                channel=channel_name,
                period=params["period"],
                metric=params["metric"],
                limit=params["limit"],
                period_start=params["period_start"],
            )
        except RPCError as exc:
            self._raise_unavailable(exc)
        return Response({"channel": channel_name, "count": len(results), "results": results, **params})


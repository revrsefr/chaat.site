import logging
import secrets
from functools import cached_property

from django.conf import settings
from django.core import signing
from django.shortcuts import render
from django.urls import reverse
from rest_framework.exceptions import APIException, NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IRCAPIAuthPermission
from .rpc_client import RPCError
from .services import AnopeStatsService


logger = logging.getLogger(__name__)


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
    except RPCError as exc:
        logger.warning("Anope RPC unavailable during dashboard seed: %s", exc)
        initial_payload["error"] = "The IRC telemetry endpoint is temporarily unavailable."

    api_endpoints = {
        "overview": reverse("irc_api_network_overview"),
        "channels": reverse("irc_api_channels"),
        "servers": reverse("irc_api_servers"),
        "users": reverse("irc_api_users"),
        "operators": reverse("irc_api_operators"),
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


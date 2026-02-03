from __future__ import annotations


class HostChannelDefaultsMiddleware:
    """Set default webchat channels based on the request host."""

    DEFAULT_CHANNELS = "#amistad,#general"
    CHAAT_CHANNELS = "#!accueil"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = (request.get_host() or "").split(":", 1)[0].lower()
        if host in {
            "chaat.site",
            "www.chaat.site",
            "europnet.chat",
            "www.europnet.chat",
            "europnet.site",
            "www.europnet.site",
        }:
            request.webchat_channel_default = self.CHAAT_CHANNELS
        else:
            request.webchat_channel_default = self.DEFAULT_CHANNELS

        return self.get_response(request)

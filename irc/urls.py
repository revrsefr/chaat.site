from django.urls import path

from .views import (
    ChanstatsPlusTopChannelsView,
    ChanstatsPlusTopInChannelView,
    ChanstatsPlusTopNicksGlobalView,
    ChannelDetailView,
    ChannelListView,
    NetworkOverviewView,
    TelemetryHistoryView,
    OperatorListView,
    ServerDetailView,
    ServerListView,
    UserDetailView,
    UserListView,
    dashboard,
    webchat,
)


urlpatterns = [
    path('webchat/', webchat, name='webchat'),
    path("dashboard/", dashboard, name="irc_dashboard"),

    # API surface
    path("api/network/overview/", NetworkOverviewView.as_view(), name="irc_api_network_overview"),
    path("api/network/history/", TelemetryHistoryView.as_view(), name="irc_api_history"),
    path("api/channels/", ChannelListView.as_view(), name="irc_api_channels"),
    path("api/channels/<path:channel_name>/", ChannelDetailView.as_view(), name="irc_api_channel_detail"),
    path("api/servers/", ServerListView.as_view(), name="irc_api_servers"),
    path("api/servers/<str:server_name>/", ServerDetailView.as_view(), name="irc_api_server_detail"),
    path("api/users/", UserListView.as_view(), name="irc_api_users"),
    path("api/users/<str:nickname>/", UserDetailView.as_view(), name="irc_api_user_detail"),
    path("api/operators/", OperatorListView.as_view(), name="irc_api_operators"),

    # chanstats_plus (stats)
    path(
        "api/stats/chanstatsplus/top-channels/",
        ChanstatsPlusTopChannelsView.as_view(),
        name="irc_api_chanstatsplus_top_channels",
    ),
    path(
        "api/stats/chanstatsplus/top-nicks-global/",
        ChanstatsPlusTopNicksGlobalView.as_view(),
        name="irc_api_chanstatsplus_top_nicks_global",
    ),
    path(
        "api/stats/chanstatsplus/top/<path:channel_name>/",
        ChanstatsPlusTopInChannelView.as_view(),
        name="irc_api_chanstatsplus_top_in_channel",
    ),
]

from django.urls import path

from .views import (
    ChannelDetailView,
    ChannelListView,
    NetworkOverviewView,
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
    path("api/channels/", ChannelListView.as_view(), name="irc_api_channels"),
    path("api/channels/<path:channel_name>/", ChannelDetailView.as_view(), name="irc_api_channel_detail"),
    path("api/servers/", ServerListView.as_view(), name="irc_api_servers"),
    path("api/servers/<str:server_name>/", ServerDetailView.as_view(), name="irc_api_server_detail"),
    path("api/users/", UserListView.as_view(), name="irc_api_users"),
    path("api/users/<str:nickname>/", UserDetailView.as_view(), name="irc_api_user_detail"),
    path("api/operators/", OperatorListView.as_view(), name="irc_api_operators"),
]

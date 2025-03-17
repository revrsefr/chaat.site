from django.shortcuts import render
from django.shortcuts import render
from .rpc_client import AnopeRPC



def webchat(request):
    return render(request, 'irc/webchat.html')

def dashboard(request):
    rpc = AnopeRPC()
    channels = rpc.list_channels() or []
    users = rpc.list_users() or []

    channel_data = []
    for channel in channels:
        data = rpc.get_channel(channel)
        if data:
            data["user_count"] = len(data.get("users", []))  # Count users in each channel
            channel_data.append(data)

    context = {
        "channels": channel_data,
        "users": users
    }
    return render(request, "irc/dashboard.html", context)


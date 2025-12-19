from django.shortcuts import render
from locations.models import City
from accounts.models import CustomUser
from django.http import HttpResponse
from django.template.loader import render_to_string
from irc.rpc_client import AnopeRPC
from blog.models import BlogPost
from django.http import JsonResponse  
from django.conf import settings

def home(request):
    members = CustomUser.objects.all()
    latest_posts = BlogPost.objects.filter(is_published=True).order_by("-created_at")[:3]  # ✅ Get latest 3 posts
    cities = City.objects.all().order_by("name")

    rpc = AnopeRPC(token=settings.ANOPE_RPC_TOKEN)
    users = rpc.list_users() or []
    servers = rpc.run("anope.listServers") or []  # ✅ Get list of servers
    opers = rpc.run("anope.listOpers") or []  # ✅ Get list of online operators
    channels = rpc.list_channels() or []  # ✅ Get list of channels

    user_count = len(users)  # ✅ Count total connected users
    server_count = len(servers)  # ✅ Count total servers online
    oper_count = len(opers)  # ✅ Count total IRC operators online
    channel_count = len(channels)  # ✅ Count total channels

    return render(request, 'main/home.html', {
        "members": members,
        "cities": cities,
        "latest_posts": latest_posts,
        "user_count": user_count,  # ✅ Added user count
        "server_count": server_count,  # ✅ Added server count
        "oper_count": oper_count,  # ✅ Added operator count
        "channel_count": channel_count  # ✅ Added channel count
    })


def sitemap_xslt(request):
    xml = render_to_string('sitemap.xslt')
    return HttpResponse(xml, content_type='text/xml')


def save_cookie_consent(request):
    if request.method == "POST":
        analytics = request.POST.get('analytics', 'no')
        functional = request.POST.get('functional', 'no')
        advertising = request.POST.get('advertising', 'no')

        response = JsonResponse({"status": "success"})
        response.set_cookie("cookie_consent", "accepted", max_age=365*24*60*60)  # 1 year
        response.set_cookie("cookie_analytics", analytics, max_age=365*24*60*60)
        response.set_cookie("cookie_functional", functional, max_age=365*24*60*60)
        response.set_cookie("cookie_advertising", advertising, max_age=365*24*60*60)

        return response
    return JsonResponse({"status": "error"}, status=400)
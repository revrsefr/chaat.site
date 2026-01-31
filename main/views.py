from django.shortcuts import render
from accounts.models import CustomUser
from django.http import HttpResponse
from django.template.loader import render_to_string
from irc.rpc_client import AnopeRPC
from blog.models import BlogPost
from django.http import JsonResponse  
from django.conf import settings

from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.generic import TemplateView

from .models import LegalMentions

def webirc(request):
    from django.template import TemplateDoesNotExist
    try:
        return render(request, 'webirc.html')
    except TemplateDoesNotExist:
        return HttpResponse('ERROR: webirc.html template not found in templates directory.', status=500)

@ensure_csrf_cookie
def home(request):
    latest_members = (
        CustomUser.objects.filter(public=True)
        .order_by("-date_joined")
        .only("username", "avatar", "last_login")[:9]
    )

    home_members = (
        CustomUser.objects.filter(public=True)
        .order_by("-last_login")
        .only("username", "avatar", "last_login")[:8]
    )
    latest_posts = BlogPost.objects.filter(is_published=True).order_by("-created_at")[:6]  # ✅ Get latest 6 posts

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
        "latest_members": latest_members,
        "home_members": home_members,
        "latest_posts": latest_posts,
        "posts": latest_posts,
        "user_count": user_count,  # ✅ Added user count
        "server_count": server_count,  # ✅ Added server count
        "oper_count": oper_count,  # ✅ Added operator count
        "channel_count": channel_count  # ✅ Added channel count
    })


def sitemap_xslt(request):
    xml = render_to_string('sitemap.xslt')
    return HttpResponse(xml, content_type='text/xml')


def robots_txt(request):
    content = render_to_string('robots.txt')
    return HttpResponse(content, content_type='text/plain')


@csrf_exempt
def save_cookie_consent(request):
    if request.method == "POST":
        analytics = request.POST.get('analytics', 'no')
        functional = request.POST.get('functional', 'no')
        advertising = request.POST.get('advertising', 'no')

        consent = "custom"
        if analytics == "yes" and functional == "yes" and advertising == "yes":
            consent = "accepted"
        elif analytics == "no" and functional == "no" and advertising == "no":
            consent = "declined"

        response = JsonResponse({"status": "success"})
        response.set_cookie("cookie_consent", consent, max_age=365*24*60*60)  # 1 year
        response.set_cookie("cookie_analytics", analytics, max_age=365*24*60*60)
        response.set_cookie("cookie_functional", functional, max_age=365*24*60*60)
        response.set_cookie("cookie_advertising", advertising, max_age=365*24*60*60)

        return response
    return JsonResponse({"status": "error"}, status=400)


class LegalView(TemplateView):
    template_name = "main/pages/legal.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["legal"] = LegalMentions.get_solo()
        return context
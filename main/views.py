from django.shortcuts import render
from accounts.models import CustomUser
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.core.cache import cache
from django.contrib.sites.requests import RequestSite
from irc.services import AnopeStatsService
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
    host = (request.get_host() or "").split(":", 1)[0].lower()
    cache_ns = f"home.{host}" if host else "home"

    latest_members = cache.get_or_set(
        f"{cache_ns}.latest_members",
        lambda: list(
            CustomUser.objects.filter(public=True)
            .order_by("-date_joined")
            .only("username", "avatar", "last_login")[:9]
        ),
        settings.HOME_CACHE_TTL_MEMBERS,
    )

    home_members = cache.get_or_set(
        f"{cache_ns}.home_members",
        lambda: list(
            CustomUser.objects.filter(public=True)
            .order_by("-last_login")
            .only("username", "avatar", "last_login")[:8]
        ),
        settings.HOME_CACHE_TTL_MEMBERS,
    )

    latest_posts = cache.get_or_set(
        f"{cache_ns}.latest_posts",
        lambda: list(
            BlogPost.objects.filter(is_published=True)
            .select_related("author")
            .order_by("-created_at")[:6]
        ),
        settings.HOME_CACHE_TTL_POSTS,
    )

    stats_service = AnopeStatsService()
    overview = stats_service.network_overview_cached() or {}
    counts = overview.get("counts", {}) if isinstance(overview, dict) else {}
    user_count = int(counts.get("users", 0))
    server_count = int(counts.get("servers", 0))
    oper_count = int(counts.get("operators", 0))
    channel_count = int(counts.get("channels", 0))

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
    site = RequestSite(request)
    content = render_to_string('robots.txt', {
        "site_domain": site.domain,
    })
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
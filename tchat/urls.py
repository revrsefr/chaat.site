from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.contrib.sites.requests import RequestSite
from django.http import Http404, HttpResponse
from django.template.loader import render_to_string
from main.sitemaps import StaticViewSitemap, UserSitemap, BlogSitemap
from accounts.admin import AdminLoginView
from main.views import robots_txt, home
sitemaps = {
    'static': StaticViewSitemap(),
    'profiles': UserSitemap(),
    'blog': BlogSitemap(),
}


def sitemap_index(request):
    # Custom index view (Django 5.1's built-in index() doesn't accept a 'site' kwarg).
    # We render Django's built-in sitemap templates but force host+protocol so we don't
    # depend on the Sites framework's default domain (often example.com).
    site = RequestSite(request)
    entries = []
    for section_name, sitemap_obj in sitemaps.items():
        loc_path = f"/sitemap-{section_name}.xml"
        location = f"https://{site.domain}{loc_path}"

        last_mod = None
        try:
            last_mod = sitemap_obj.get_latest_lastmod()
        except Exception:
            last_mod = None

        entries.append({"location": location, "last_mod": last_mod})

    xml = render_to_string("sitemap_index.xml", {"sitemaps": entries})
    return HttpResponse(xml, content_type="application/xml")


def sitemap_section(request, section):
    sitemap_obj = sitemaps.get(section)
    if sitemap_obj is None:
        raise Http404("No sitemap available for this section")

    urls = sitemap_obj.get_urls(site=RequestSite(request), protocol="https")
    xml = render_to_string("sitemap.xml", {"urlset": urls})
    return HttpResponse(xml, content_type="application/xml")


# Non-translated URLs (DO NOT use i18n_patterns for static!)
urlpatterns = [
    path('admin/', admin.site.urls),
    path("admin/login/", AdminLoginView.as_view(), name="admin_login"),
    path('i18n/', include('django.conf.urls.i18n')),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('robot.txt', robots_txt, name='robot_txt'),
    path('', home, name='home'),
    path("main/", include("main.urls", namespace="main")), 
    path('accounts/', include('accounts.urls')), 
    path('irc/', include('irc.urls')),    # IRC app URLs
    path('help/', include(('helpdocs.urls', 'helpdocs'), namespace='helpdocs')),
    path('community/', include('community.urls')),
    path('blog/', include('blog.urls')),
    path('locations/', include('locations.urls')),
    path('recaptcha/', include(('recaptcha.urls', 'recaptcha'), namespace='recaptcha')),
    # Sitemap index + per-section sitemaps
    path('sitemap.xml', sitemap_index, name='sitemap-index'),
    path('sitemap-<section>.xml', sitemap_section, name='sitemap-section'),
    
]
# ✅ Static & Media URLs must NOT be inside i18n_patterns!
if settings.DEBUG:  
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

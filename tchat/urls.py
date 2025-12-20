from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.contrib.sitemaps.views import sitemap
from main.sitemaps import StaticViewSitemap, UserSitemap, BlogSitemap
from django.shortcuts import redirect
from accounts.admin import AdminLoginView



def home_redirect(request):
    return redirect('/main/home/', permanent=True)  # ✅ 301 Redirect


sitemaps = {
    'static': StaticViewSitemap(),
    'profiles': UserSitemap(),
    'blog': BlogSitemap(),
}


# Non-translated URLs (DO NOT use i18n_patterns for static!)
urlpatterns = [
    path('admin/', admin.site.urls),
    path("admin/login/", AdminLoginView.as_view(), name="admin_login"),
    path('', home_redirect, name='home'),  # ✅ Global `home` (redirects `/` -> `/main/home/`)
    path("main/", include("main.urls", namespace="main")), 
    path('accounts/', include('accounts.urls')), 
    path('irc/', include('irc.urls')),    # IRC app URLs
    path('community/', include('community.urls')),
    path('blog/', include('blog.urls')),
    path('locations/', include('locations.urls')),
    path('recaptcha/', include(('recaptcha.urls', 'recaptcha'), namespace='recaptcha')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    
]
# ✅ Static & Media URLs must NOT be inside i18n_patterns!
if settings.DEBUG:  
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

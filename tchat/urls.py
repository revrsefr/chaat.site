from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns


# Non-translated URLs (DO NOT use i18n_patterns for static!)
urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path('accounts/', include('accounts.urls')), 
    path('irc/', include('irc.urls')),    # IRC app URLs
    path('community/', include('community.urls')),
    path('main/', include('main.urls')), 
    path('blog/', include('blog.urls')), 
]
# ✅ Static & Media URLs must NOT be inside i18n_patterns!
if settings.DEBUG:  
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

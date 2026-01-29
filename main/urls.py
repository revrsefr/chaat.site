from django.urls import path
from .views import home, save_cookie_consent, webirc, LegalView
from django.views.generic import TemplateView, RedirectView

app_name = "main"  # ✅ Set namespace for the 'main' app

urlpatterns = [
    # Legacy URL kept for backward compatibility; canonical home is now '/'
    path("home/", RedirectView.as_view(url="/", permanent=True), name="home"),
    path("webirc/", webirc, name="webirc"),
    path('sitemap.xsl', TemplateView.as_view(template_name="sitemap.xsl"), name='sitemap_xslt'),
    path('cookie-consent/', save_cookie_consent, name='cookie_consent'),

    # Simple informational pages (used by the footer)
    path("about/", TemplateView.as_view(template_name="main/pages/about.html"), name="about"),
    path("terms/", TemplateView.as_view(template_name="main/pages/terms.html"), name="terms"),
    path("legal/", LegalView.as_view(), name="legal"),
]
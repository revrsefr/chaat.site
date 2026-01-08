from django.urls import path
from .views import home, save_cookie_consent, webirc
from django.views.generic import TemplateView

app_name = "main"  # ✅ Set namespace for the 'main' app

urlpatterns = [
    path("home/", home, name="home"),  # ✅ Named URL for 'home'
    path("webirc/", webirc, name="webirc"),
    path('sitemap.xsl', TemplateView.as_view(template_name="sitemap.xsl"), name='sitemap_xslt'),
    path('cookie-consent/', save_cookie_consent, name='cookie_consent'),

    # Simple informational pages (used by the footer)
    path("about/", TemplateView.as_view(template_name="main/pages/about.html"), name="about"),
    path("terms/", TemplateView.as_view(template_name="main/pages/terms.html"), name="terms"),
    path("legal/", TemplateView.as_view(template_name="main/pages/legal.html"), name="legal"),
]
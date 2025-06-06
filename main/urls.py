from django.urls import path
from .views import home, save_cookie_consent
from django.views.generic import TemplateView

app_name = "main"  # ✅ Set namespace for the 'main' app

urlpatterns = [
    path("home/", home, name="home"),  # ✅ Named URL for 'home'
    path('sitemap.xsl', TemplateView.as_view(template_name="sitemap.xsl"), name='sitemap_xslt'),
    path('cookie-consent/', save_cookie_consent, name='cookie_consent'),
]
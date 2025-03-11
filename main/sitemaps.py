from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from accounts.models import CustomUser  
from blog.models import BlogPost

class StaticViewSitemap(Sitemap):
    priority = 1.0
    changefreq = "daily"
    protocol = "https"

    def items(self):
        return ['main:home']

    def location(self, item):
        return reverse(item)

class UserSitemap(Sitemap):
    priority = 0.7
    changefreq = "weekly"
    protocol = "https"

    def items(self):
        return CustomUser.objects.filter(is_active=True)

    def location(self, obj):
        return f"/accounts/profile/{obj.username}/"

class BlogSitemap(Sitemap):
    priority = 0.7
    changefreq = "weekly"
    protocol = "https"

    def items(self):
        return BlogPost.objects.filter(is_active=True)

    def location(self, obj):
        return reverse("blog:blog_detail", kwargs={"slug": obj.slug})
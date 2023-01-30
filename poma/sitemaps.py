from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from app.models import Post


class PostSitemap(Sitemap):
    changefreq = "always"
    priority = 0.5

    def items(self):
        return Post.objects.all()

    def lastmod(self, obj):
        return obj.modified_at

    def get_domain(self, *args):
        return "app.pomasearch.com"


class StaticViewSitemap(Sitemap):
    priority = 1.0
    changefreq = "daily"

    def items(self):
        return ["home"]

    def location(self, item):
        return reverse(item)

    def get_domain(self, *args):
        return "app.pomasearch.com"


sitemaps = {"posts": PostSitemap, "static": StaticViewSitemap}

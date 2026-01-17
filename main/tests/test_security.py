from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase, override_settings


class SafeUrlFilterTests(SimpleTestCase):
    def test_safe_url_blocks_javascript_scheme(self):
        tmpl = Template('{% load safe_url %}<a href="{{ u|safe_url }}">x</a>')
        rendered = tmpl.render(Context({"u": "javascript:alert(1)"}))
        self.assertIn('href="#"', rendered)

    def test_safe_url_allows_https(self):
        tmpl = Template('{% load safe_url %}<a href="{{ u|safe_url }}">x</a>')
        rendered = tmpl.render(Context({"u": "https://example.com/path"}))
        self.assertIn('href="https://example.com/path"', rendered)


class FooterContextProcessorTests(SimpleTestCase):
    @override_settings(
        SITE_FOOTERS={
            "chaat.site": {
                "information_links": [{"label": "Evil", "url": "javascript:alert(1)"}],
                "useful_links": [{"label": "Ok", "url": "https://example.com"}],
                "social_links": [{"label": "Also evil", "url": "data:text/html,boom"}],
                "recent_articles_count": 0,
                "latest_users_count": 0,
            }
        }
    )
    def test_site_footer_sanitizes_configured_link_urls(self):
        from tchat.context_processors import site_footer

        rf = RequestFactory()
        request = rf.get("/", HTTP_HOST="chaat.site")

        ctx = site_footer(request)
        footer = ctx["footer"]

        self.assertEqual(footer["information_links"][0]["url"], "#")
        self.assertEqual(footer["useful_links"][0]["url"], "https://example.com")
        self.assertEqual(footer["social_links"][0]["url"], "#")

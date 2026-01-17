from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from django.core.cache import cache
from django.contrib.auth import get_user_model


class RegisterValidateViewTests(TestCase):
    def test_register_validate_returns_field_errors(self):
        url = reverse("register_validate")
        resp = self.client.post(url, data={
            "username": "x",
            "email": "not-an-email",
            "password1": "123",
            "password2": "456",
            "birthday": "not-a-date",
            "gender": "",
            "city": "",
        }, secure=True)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("ok"))
        fe = data.get("field_errors") or {}
        self.assertIn("email", fe)
        self.assertIn("password1", fe)
        self.assertIn("password2", fe)
        self.assertIn("birthday", fe)
        self.assertIn("gender", fe)
        self.assertIn("city", fe)

    @override_settings(REGISTER_PREFLIGHT_CHECK_AVAILABILITY=True)
    def test_register_validate_reports_existing_username_and_email_when_enabled(self):
        User = get_user_model()
        User.objects.create_user(username="reverse", email="reverse@example.com", password="passw0rd-123")

        url = reverse("register_validate")
        resp = self.client.post(url, data={
            "username": "reverse",
            "email": "reverse@example.com",
            "password1": "passw0rd-123",
            "password2": "passw0rd-123",
            "birthday": "2000-01-01",
            "gender": "M",
            "city": "Paris",
        }, secure=True)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("ok"))
        fe = data.get("field_errors") or {}
        self.assertIn("username", fe)
        self.assertIn("email", fe)

    @override_settings(REGISTER_PREFLIGHT_VALIDATE_PER_MINUTE=1)
    def test_register_validate_rate_limits(self):
        try:
            cache.clear()
        except Exception:
            pass

        url = reverse("register_validate")
        payload = {
            "username": "okname",
            "email": "ok@example.com",
            "password1": "passw0rd-123",
            "password2": "passw0rd-123",
            "birthday": "2000-01-01",
            "gender": "M",
            "city": "Paris",
        }
        r1 = self.client.post(url, data=payload, secure=True)
        self.assertEqual(r1.status_code, 200)
        r2 = self.client.post(url, data=payload, secure=True)
        self.assertEqual(r2.status_code, 429)

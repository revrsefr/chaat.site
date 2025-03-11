import requests
from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin

class AdminRecaptchaMiddleware(MiddlewareMixin):
    """ Middleware to protect /admin with Google reCAPTCHA v2 """

    def process_request(self, request):
        # ✅ Only protect the Django admin login page
        if request.path.startswith("/admin/login/") and request.method == "POST":
            recaptcha_response = request.POST.get("g-recaptcha-response")

            if not recaptcha_response:
                return redirect_to_login(request.get_full_path(), "/admin/login/")

            # ✅ Verify reCAPTCHA with Google
            data = {
                "secret": settings.RECAPTCHA_SECRET_KEY,
                "response": recaptcha_response
            }
            google_response = requests.post(
                "https://www.google.com/recaptcha/api/siteverify",
                data=data
            ).json()

            if not google_response.get("success"):
                return redirect("/admin/login/")  # Block login if reCAPTCHA fails

import requests
from django.conf import settings

def verify_recaptcha(recaptcha_response):
    """Verify reCAPTCHA token using Google's API."""
    recaptcha_verify_url = "https://www.google.com/recaptcha/api/siteverify"
    recaptcha_data = {
        "secret": settings.RECAPTCHA_SECRET_KEY,
        "response": recaptcha_response
    }
    try:
        recaptcha_result = requests.post(recaptcha_verify_url, data=recaptcha_data).json()
        if recaptcha_result.get("success", False):
            return True, None
        return False, recaptcha_result.get("error-codes", "Unknown reCAPTCHA error.")
    except requests.RequestException:
        return False, "Failed to verify reCAPTCHA. Please try again."

import requests
from django.conf import settings
from django.core.cache import cache

def verify_recaptcha(token):
    if not token:
        return False, "reCAPTCHA token is missing"

    cache_key = f"recaptcha_{token}"
    cached_result = cache.get(cache_key)

    if cached_result is not None:
        return cached_result["success"], cached_result.get("error", "reCAPTCHA validation failed.")

    url = "https://www.google.com/recaptcha/api/siteverify"
    payload = {
        "secret": settings.RECAPTCHA_PRIVATE_KEY,
        "response": token,
    }

    try:
        response = requests.post(url, data=payload, timeout=5)
        result = response.json()

        cache.set(cache_key, result, timeout=300)

        if result.get("success"):
            return True, None
        else:
            return False, result.get("error-codes", "reCAPTCHA validation failed.")

    except requests.RequestException as e:
        return False, f"reCAPTCHA request failed: {str(e)}"

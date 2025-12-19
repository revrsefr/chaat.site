import logging
import requests
from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from recaptcha.jwt_utils import decode_jwt
from django.utils.timezone import now
from recaptcha.models import VerificationToken
from django.utils.timezone import now
from django.core.cache import cache
from django.views.decorators.http import require_GET
from django.http import JsonResponse
from datetime import timedelta


logger = logging.getLogger(__name__)

def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0]  # First IP in the list is the real client
    return request.META.get("REMOTE_ADDR", "0.0.0.0")  # Fallback to REMOTE_ADDR

@require_GET
def check_token(request):
    client_ip = get_client_ip(request)
    allowed_ips = getattr(settings, "RECAPTCHA_CHECK_IPS", ["54.38.156.235", "2001:41d0:701:1100::65d0", "::1", "127.0.0.1"])
    if client_ip not in allowed_ips:
        return render(request, "recaptcha/error.html", {
            "message": "Access denied: You are not authorized to use this service."
        }, status=403)

    jwt_token = request.GET.get("token")
    if not jwt_token:
        return JsonResponse({"verified": False})

    payload = decode_jwt(jwt_token, settings.EXTJWT_SECRET, settings.JWT_ISSUER)
    if not payload:
        return JsonResponse({"verified": False})

    verified = VerificationToken.objects.filter(
        token=jwt_token,
        is_verified=True,
        created_at__gte=now() - timedelta(minutes=30)
    ).exists()

    return JsonResponse({"verified": verified})

def verify_session_token(request):
    jwt_token = request.GET.get("token")
    client_ip = request.META.get('REMOTE_ADDR')

    if not jwt_token:
        return render(request, "recaptcha/error.html", {
            "message": "Missing JWT token. Reconnect to IRC."
        })

    attempts_key = f"verify_page_attempts:{client_ip}"
    attempts = cache.get(attempts_key, 0)

    if attempts >= 10:
        return render(request, "recaptcha/error.html", {
            "message": "Too many attempts. Please wait 10 minutes."
        })

    payload = decode_jwt(jwt_token, settings.EXTJWT_SECRET, settings.JWT_ISSUER)
    if not payload:
        cache.set(attempts_key, attempts + 1, timeout=600)
        return render(request, "recaptcha/error.html", {
            "message": "Invalid or expired token. Reconnect to IRC."
        })

    # <-- Explicitly check if token is already verified -->
    if VerificationToken.objects.filter(token=jwt_token, is_verified=True).exists():
        return render(request, "recaptcha/error.html", {
            "message": "This token has already been used. Reconnect to IRC for a new verification token."
        })

    nickname = payload.get("sub")

    return render(request, "recaptcha/verify.html", {
        "jwt": jwt_token,
        "nickname": nickname,
        "site_key": settings.RECAPTCHA_SITE_KEY,
    })


def process_recaptcha(request):
    client_ip = request.META.get('REMOTE_ADDR')

    cache_key = f"recaptcha_attempts:{client_ip}"
    attempts = cache.get(cache_key, 0)

    if attempts >= 5:
        return JsonResponse({"status": "error", "message": "Too many attempts, please wait 10 minutes."})

    recaptcha_response = request.POST.get('g-recaptcha-response')
    jwt_token = request.POST.get('jwt')

    if not recaptcha_response or not jwt_token:
        cache.set(cache_key, attempts + 1, timeout=600)
        return JsonResponse({"status": "error", "message": "Missing required fields."})

    payload = decode_jwt(jwt_token, settings.EXTJWT_SECRET, settings.JWT_ISSUER)
    if not payload:
        cache.set(cache_key, attempts + 1, timeout=600)
        return JsonResponse({"status": "error", "message": "Invalid or expired JWT."})

    # Already verified?
    if VerificationToken.objects.filter(token=jwt_token, is_verified=True).exists():
        return JsonResponse({"status": "error", "message": "Token already verified."})

    # Verify reCAPTCHA response with Google
    response = requests.post(
        "https://www.google.com/recaptcha/api/siteverify",
        data={
            "secret": settings.RECAPTCHA_SECRET_KEY,
            "response": recaptcha_response,
        }
    )
    result = response.json()

    if not result.get("success"):
        cache.set(cache_key, attempts + 1, timeout=600)
        return JsonResponse({"status": "error", "message": "reCAPTCHA verification failed."})

    # ONLY HERE: Mark JWT as verified (single clear point)
    VerificationToken.objects.update_or_create(
        token=jwt_token,
        defaults={"is_verified": True, "created_at": now()}
    )

    cache.delete(cache_key)

    return JsonResponse({"status": "ok", "result": jwt_token})

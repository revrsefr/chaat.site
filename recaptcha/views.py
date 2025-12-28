import logging
import requests
import hmac
import hashlib
from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from recaptcha.jwt_utils import decode_jwt
from recaptcha.models import VerificationToken, TrustedIP
from django.utils.timezone import now
from django.core.cache import cache
from django.views.decorators.http import require_GET
from datetime import timedelta


logger = logging.getLogger(__name__)

def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0]  # First IP in the list is the real client
    return request.META.get("REMOTE_ADDR", "0.0.0.0")  # Fallback to REMOTE_ADDR


def get_remote_addr(request):
    """Returns the actual TCP peer address (do not trust XFF for allowlisting)."""

    return request.META.get("REMOTE_ADDR", "0.0.0.0")


def _ip_hash_key_bytes():
    # Prefer a dedicated pepper; fall back to SECRET_KEY.
    key = getattr(settings, "RECAPTCHA_IP_HASH_KEY", None) or settings.SECRET_KEY
    if isinstance(key, str):
        return key.encode("utf-8")
    return key


def hash_ip(ip: str) -> str:
    """Keyed hash (HMAC-SHA256) for an IP address."""

    ip = (ip or "").strip()
    return hmac.new(_ip_hash_key_bytes(), ip.encode("utf-8"), hashlib.sha256).hexdigest()


def is_ip_trusted(ip: str) -> bool:
    # Opportunistic cleanup.
    TrustedIP.objects.filter(expires_at__lt=now()).delete()

    digest = hash_ip(ip)
    updated = TrustedIP.objects.filter(ip_hash=digest, expires_at__gte=now()).update(last_seen=now())
    return updated > 0


def remember_trusted_ip(ip: str, days: int = 7) -> None:
    days = int(getattr(settings, "RECAPTCHA_TRUST_IP_DAYS", days))
    digest = hash_ip(ip)
    TrustedIP.objects.update_or_create(
        ip_hash=digest,
        defaults={
            "last_seen": now(),
            "expires_at": now() + timedelta(days=days),
        },
    )

@require_GET
def check_token(request):
    # This is a server-to-server endpoint (IRCd -> Django). Never trust X-Forwarded-For here.
    client_ip = get_remote_addr(request)
    allowed_ips = getattr(settings, "RECAPTCHA_CHECK_IPS", ["54.38.156.235", "2001:41d0:701:1100::65d0", "::1", "127.0.0.1"])
    if client_ip not in allowed_ips:
        return render(request, "recaptcha/error.html", {
            "message": "Accès refusé : vous n’êtes pas autorisé à utiliser ce service."
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


@require_GET
def check_trusted_token(request):
    """Server-to-server: returns whether the *IP inside a valid JWT* is trusted.

    Intended use: the IRCd generates a JWT, then asks Django if the IP inside that
    JWT is currently trusted (7 days). If yes, IRCd can skip forcing reCAPTCHA.
    """

    caller_ip = get_remote_addr(request)
    allowed_ips = getattr(settings, "RECAPTCHA_CHECK_IPS", ["54.38.156.235", "2001:41d0:701:1100::65d0", "::1", "127.0.0.1"])
    if caller_ip not in allowed_ips:
        return JsonResponse({"trusted": False}, status=403)

    jwt_token = request.GET.get("token")
    if not jwt_token:
        return JsonResponse({"trusted": False})

    payload = decode_jwt(jwt_token, settings.EXTJWT_SECRET, settings.JWT_ISSUER)
    if not payload:
        return JsonResponse({"trusted": False})

    token_ip = payload.get("ip")
    if not token_ip:
        return JsonResponse({"trusted": False})

    return JsonResponse({"trusted": is_ip_trusted(token_ip)})

def verify_session_token(request):
    jwt_token = request.GET.get("token")
    client_ip = get_client_ip(request)

    if not jwt_token:
        return render(request, "recaptcha/error.html", {
            "message": "Jeton manquant. Reconnectez-vous à IRC et réessayez."
        })

    attempts_key = f"verify_page_attempts:{client_ip}"
    attempts = cache.get(attempts_key, 0)

    if attempts >= 10:
        return render(request, "recaptcha/error.html", {
            "message": "Trop de tentatives. Veuillez patienter 10 minutes avant de réessayer."
        })

    payload = decode_jwt(jwt_token, settings.EXTJWT_SECRET, settings.JWT_ISSUER)
    if not payload:
        cache.set(attempts_key, attempts + 1, timeout=600)
        return render(request, "recaptcha/error.html", {
            "message": "Jeton invalide ou expiré. Reconnectez-vous à IRC pour obtenir un nouveau lien."
        })

    token_ip = payload.get("ip")
    if not token_ip:
        cache.set(attempts_key, attempts + 1, timeout=600)
        return render(request, "recaptcha/error.html", {
            "message": "Ce lien n’est pas associé à une adresse IP. Reconnectez-vous à IRC pour obtenir un nouveau lien de vérification."
        })

    if token_ip != client_ip:
        cache.set(attempts_key, attempts + 1, timeout=600)
        return render(request, "recaptcha/error.html", {
            "message": "Adresse IP différente pour ce lien. Merci d’ouvrir le lien depuis le même appareil et la même connexion que votre session IRC."
        })

    # <-- Explicitly check if token is already verified -->
    if VerificationToken.objects.filter(token=jwt_token, is_verified=True).exists():
        return render(request, "recaptcha/error.html", {
            "message": "Ce jeton a déjà été utilisé. Reconnectez-vous à IRC pour obtenir un nouveau jeton de vérification."
        })

    nickname = payload.get("sub")

    return render(request, "recaptcha/verify.html", {
        "jwt": jwt_token,
        "nickname": nickname,
        "site_key": settings.RECAPTCHA_SITE_KEY,
    })


def process_recaptcha(request):
    client_ip = get_client_ip(request)

    cache_key = f"recaptcha_attempts:{client_ip}"
    attempts = cache.get(cache_key, 0)

    if attempts >= 5:
        return JsonResponse({"status": "error", "message": "Trop de tentatives. Veuillez patienter 10 minutes avant de réessayer."})

    recaptcha_response = request.POST.get('g-recaptcha-response')
    jwt_token = request.POST.get('jwt')

    if not recaptcha_response or not jwt_token:
        cache.set(cache_key, attempts + 1, timeout=600)
        return JsonResponse({"status": "error", "message": "Champs requis manquants. Merci de réessayer."})

    payload = decode_jwt(jwt_token, settings.EXTJWT_SECRET, settings.JWT_ISSUER)
    if not payload:
        cache.set(cache_key, attempts + 1, timeout=600)
        return JsonResponse({"status": "error", "message": "JWT invalide ou expiré. Reconnectez-vous à IRC pour obtenir un nouveau lien."})

    token_ip = payload.get("ip")
    if not token_ip:
        cache.set(cache_key, attempts + 1, timeout=600)
        return JsonResponse({"status": "error", "message": "Ce lien n’est pas associé à une adresse IP. Reconnectez-vous à IRC pour obtenir un nouveau lien."})

    if token_ip != client_ip:
        cache.set(cache_key, attempts + 1, timeout=600)
        return JsonResponse({"status": "error", "message": "Adresse IP différente pour ce jeton. Merci d’ouvrir le lien depuis le même appareil et la même connexion que votre session IRC."})

    # Already verified?
    if VerificationToken.objects.filter(token=jwt_token, is_verified=True).exists():
        return JsonResponse({"status": "error", "message": "Ce jeton est déjà vérifié (déjà utilisé). Reconnectez-vous à IRC pour obtenir un nouveau lien."})

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
        return JsonResponse({"status": "error", "message": "Échec de la vérification reCAPTCHA. Merci de réessayer."})

    # ONLY HERE: Mark JWT as verified (single clear point)
    VerificationToken.objects.update_or_create(
        token=jwt_token,
        defaults={"is_verified": True, "created_at": now()}
    )

    # Remember this IP for a short time to reduce friction on reconnect.
    remember_trusted_ip(client_ip)

    cache.delete(cache_key)

    return JsonResponse({"status": "ok", "result": jwt_token})

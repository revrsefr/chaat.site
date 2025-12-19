import requests
from django.conf import settings

import secrets
from datetime import timedelta

from django.core.mail import send_mail
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from django.core.cache import cache
from django.core.exceptions import ValidationError

def verify_recaptcha(recaptcha_response):
    """Verify reCAPTCHA token using Google's API."""
    recaptcha_verify_url = "https://www.google.com/recaptcha/api/siteverify"
    recaptcha_data = {
        "secret": settings.RECAPTCHA_SECRET_KEY,
        "response": recaptcha_response
    }
    try:
        recaptcha_result = requests.post(recaptcha_verify_url, data=recaptcha_data, timeout=5).json()
        if recaptcha_result.get("success", False):
            return True, None
        return False, recaptcha_result.get("error-codes", "Unknown reCAPTCHA error.")
    except requests.RequestException:
        return False, "Failed to verify reCAPTCHA. Please try again."


def issue_email_verification_code(user, *, ttl_minutes: int = 20) -> str:
    """Generate a short verification code, store its hash on the user, and email it.

    Returns the plain code (useful for tests/logs). In production, do not display it.
    """

    # Basic resend cooldown to reduce spam and brute-force assistance.
    cooldown_seconds = int(getattr(settings, "EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS", 60))
    if user.email_verification_sent_at and (timezone.now() - user.email_verification_sent_at).total_seconds() < cooldown_seconds:
        raise ValidationError("Cooldown")

    previous_hash = user.email_verification_code_hash
    previous_sent_at = user.email_verification_sent_at
    previous_expires_at = user.email_verification_expires_at

    code = f"{secrets.randbelow(1_000_000):06d}"
    code_hash = make_password(code)
    sent_at = timezone.now()
    expires_at = sent_at + timedelta(minutes=ttl_minutes)

    subject = getattr(settings, "EMAIL_VERIFICATION_SUBJECT", "Votre code de confirmation")
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
    site_name = getattr(settings, "SITE_NAME", None) or getattr(settings, "EMAIL_SITE_NAME", "chaat.site")

    message = (
        f"Bonjour {user.username},\n\n"
        f"Voici votre code de confirmation pour {site_name}: {code}\n\n"
        f"Ce code expirera dans {ttl_minutes} minutes.\n\n"
        "Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.\n"
    )

    try:
        # Let send_mail raise if misconfigured; callers can catch and return a nice API error.
        send_mail(subject, message, from_email, [user.email], fail_silently=False)
    except Exception:
        # Restore previous code state if sending fails.
        user.email_verification_code_hash = previous_hash
        user.email_verification_sent_at = previous_sent_at
        user.email_verification_expires_at = previous_expires_at
        user.save(update_fields=[
            "email_verification_code_hash",
            "email_verification_sent_at",
            "email_verification_expires_at",
        ])
        raise

    user.email_verification_code_hash = code_hash
    user.email_verification_sent_at = sent_at
    user.email_verification_expires_at = expires_at
    user.save(update_fields=[
        "email_verification_code_hash",
        "email_verification_sent_at",
        "email_verification_expires_at",
    ])

    return code


def verify_email_code(user, code: str) -> tuple[bool, str | None]:
    """Validate a verification code for the given user."""

    if user.email_verified:
        return True, None

    if not code:
        return False, "Code requis."

    if not user.email_verification_code_hash:
        return False, "Aucun code actif. Veuillez demander un nouveau code."

    if user.email_verification_expires_at and timezone.now() > user.email_verification_expires_at:
        return False, "Code expiré. Veuillez demander un nouveau code."

    # Brute-force protection: limit attempts per user per active code.
    max_attempts = int(getattr(settings, "EMAIL_VERIFICATION_MAX_ATTEMPTS", 10))
    attempts_key = f"emailverify:attempts:{user.pk}"
    attempts = cache.get(attempts_key)
    if attempts is None:
        attempts = 0
    if attempts >= max_attempts:
        return False, "Trop de tentatives. Réessayez plus tard."

    if not check_password(code, user.email_verification_code_hash):
        # Keep attempts window aligned with code expiry.
        ttl_seconds = None
        if user.email_verification_expires_at:
            ttl_seconds = max(1, int((user.email_verification_expires_at - timezone.now()).total_seconds()))
        if attempts == 0:
            cache.set(attempts_key, 1, timeout=ttl_seconds)
        else:
            # For backends that support it, this preserves TTL (e.g., django-redis).
            # For others, TTL behavior may vary, but throttling still works.
            cache.incr(attempts_key)
        return False, "Code invalide."

    user.email_verified = True
    user.email_verification_code_hash = ""
    user.email_verification_expires_at = None
    user.save(update_fields=["email_verified", "email_verification_code_hash", "email_verification_expires_at"])
    cache.delete(f"emailverify:attempts:{user.pk}")
    return True, None

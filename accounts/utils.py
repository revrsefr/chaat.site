import requests
from django.conf import settings

import secrets
from datetime import timedelta

from django.core.mail import send_mail
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password

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


def issue_email_verification_code(user, *, ttl_minutes: int = 20) -> str:
    """Generate a short verification code, store its hash on the user, and email it.

    Returns the plain code (useful for tests/logs). In production, do not display it.
    """

    code = f"{secrets.randbelow(1_000_000):06d}"
    user.email_verification_code_hash = make_password(code)
    user.email_verification_sent_at = timezone.now()
    user.email_verification_expires_at = timezone.now() + timedelta(minutes=ttl_minutes)
    user.save(update_fields=[
        "email_verification_code_hash",
        "email_verification_sent_at",
        "email_verification_expires_at",
    ])

    subject = getattr(settings, "EMAIL_VERIFICATION_SUBJECT", "Votre code de confirmation")
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
    site_name = getattr(settings, "SITE_NAME", None) or getattr(settings, "EMAIL_SITE_NAME", "chaat.site")

    message = (
        f"Bonjour {user.username},\n\n"
        f"Voici votre code de confirmation pour {site_name}: {code}\n\n"
        f"Ce code expirera dans {ttl_minutes} minutes.\n\n"
        "Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.\n"
    )

    # Let send_mail raise if misconfigured; callers can catch and return a nice API error.
    send_mail(subject, message, from_email, [user.email], fail_silently=False)

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

    if not check_password(code, user.email_verification_code_hash):
        return False, "Code invalide."

    user.email_verified = True
    user.email_verification_code_hash = ""
    user.email_verification_expires_at = None
    user.save(update_fields=["email_verified", "email_verification_code_hash", "email_verification_expires_at"])
    return True, None

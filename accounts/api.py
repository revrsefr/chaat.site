import logging

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.hashers import check_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.utils.dateparse import parse_date

from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import jwt

from accounts.models import CustomUser, IrcAppPassword
from accounts.tokens import get_tokens_for_user
from accounts.utils import issue_email_verification_code, verify_email_code

from .utils import verify_recaptcha


irc_api_logger = logging.getLogger("accounts.irc_api")
auth_api_logger = logging.getLogger("accounts.auth_api")


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def register(request):
    try:
        if request.user.is_authenticated:
            return Response({"error": "You are already registered"}, status=status.HTTP_400_BAD_REQUEST)

        username = (request.data.get("username") or "").strip()
        email = (request.data.get("email") or "").strip().lower()
        password1 = request.data.get("password1")
        password2 = request.data.get("password2")
        birthday_raw = request.data.get("birthday")
        gender = (request.data.get("gender") or "").strip()
        city = (request.data.get("city") or "").strip()
        recaptcha_token = request.data.get("g_recaptcha_response") or request.data.get("g-recaptcha-response")
        avatar = request.FILES.get("avatar")  # ✅ Get uploaded avatar file

        if not username or not email or not password1 or not password2:
            return Response({"error": "Champs requis manquants."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            EmailValidator()(email)
        except ValidationError:
            return Response({"error": "Email invalide."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate username using model field validators.
        try:
            CustomUser._meta.get_field("username").run_validators(username)
        except ValidationError:
            return Response({"error": "Nom d'utilisateur invalide."}, status=status.HTTP_400_BAD_REQUEST)

        if password1 != password2:
            return Response({"error": "Passwords do not match"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_password(password1)
        except ValidationError as ve:
            return Response({"error": "Mot de passe trop faible.", "details": list(ve.messages)}, status=status.HTTP_400_BAD_REQUEST)

        birthday = None
        if birthday_raw:
            birthday = parse_date(str(birthday_raw))
            if not birthday:
                return Response({"error": "Date de naissance invalide."}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ reCAPTCHA Verification
        is_valid, recaptcha_error = verify_recaptcha(recaptcha_token)
        if not is_valid:
            return Response({"error": f"reCAPTCHA failed: {recaptcha_error}"}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Check if username or email exists
        if CustomUser.objects.filter(username=username).exists():
            return Response({"error": "Username already exists"}, status=status.HTTP_400_BAD_REQUEST)
        if CustomUser.objects.filter(email=email).exists():
            return Response({"error": "Email already registered"}, status=status.HTTP_400_BAD_REQUEST)
        if gender not in ["M", "F"]:
            return Response({"error": "Invalid gender"}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Create user
        user = CustomUser.objects.create_user(
            username=username,
            email=email,
            age=birthday,
            gender=gender,
            city=city,
            password=password1,
        )

        # New accounts must verify email before login.
        user.email_verified = False
        user.save(update_fields=["email_verified"])  # Ensure flag is persisted.

        # ✅ Save avatar AFTER user is created
        if avatar:
            max_bytes = getattr(settings, "AVATAR_MAX_UPLOAD_SIZE", 2 * 1024 * 1024)
            content_type = getattr(avatar, "content_type", "") or ""
            if avatar.size and avatar.size > max_bytes:
                return Response({"error": "Avatar trop volumineux."}, status=status.HTTP_400_BAD_REQUEST)
            if content_type and not content_type.startswith("image/"):
                return Response({"error": "Avatar invalide."}, status=status.HTTP_400_BAD_REQUEST)
            user.avatar = avatar
            user.save(update_fields=["avatar"])  # ✅ Save the user with avatar

        # Email verification code
        try:
            issue_email_verification_code(user)
        except ValidationError as ve:
            auth_api_logger.warning("register email_issue validation_error user_id=%s email=%r err=%s", user.pk, user.email, ve)
            return Response({
                "error": "Compte créé, mais l'envoi du code est temporairement limité. Réessayez bientôt.",
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        except Exception:
            auth_api_logger.exception("register email_issue failed user_id=%s email=%r", user.pk, user.email)
            return Response({
                "error": "Compte créé, mais impossible d'envoyer l'email de confirmation. Veuillez réessayer plus tard ou contacter le support.",
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            "message": "Compte créé. En attente de confirmation par email.",
            "requires_email_verification": True,
        }, status=status.HTTP_201_CREATED)

    except Exception:
        auth_api_logger.exception("register unexpected_error")
        return Response({"error": "Internal server error."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Make ScopedRateThrottle apply the intended scope.
register.throttle_scope = "register"


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def login_api(request):
    try:
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response({"error": "Username and password are required."}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(username=username, password=password)

        if user and not getattr(user, "email_verified", False):
            return Response({"error": "Veuillez confirmer votre email avant de vous connecter."}, status=status.HTTP_403_FORBIDDEN)

        if user:
            tokens = get_tokens_for_user(user)
            return Response({
                "message": "Login successful!",
                "username": user.username, 
                "access_token": tokens["access"],
                "refresh_token": tokens["refresh"],
            }, status=status.HTTP_200_OK)
        
        return Response({"error": "Invalid username or password."}, status=status.HTTP_400_BAD_REQUEST)

    except Exception:
        auth_api_logger.exception("login_api unexpected_error")
        return Response({"error": "Internal server error."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


login_api.throttle_scope = "login"


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def login_token(request):
    """Anope-compatible login endpoint.

    Expected request: application/x-www-form-urlencoded with fields
    - username
    - password

    Response (200):
    - {"access_token": "<jwt>", "email": "user@example.com"}

    Notes:
    - If a shared secret is configured (settings.IRC_API_TOKEN), the client can send it via X-API-Key.
    - Always returns HTTP 200 so Anope can parse the JSON body (its module treats non-200 as a transport error).
    """

    # ScopedRateThrottle reads view.throttle_scope (not request.throttle_scope).

    remote_ip = request.META.get("REMOTE_ADDR")
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")

    required_api_key = getattr(settings, "IRC_API_TOKEN", None)
    if required_api_key:
        provided_api_key = request.headers.get("X-API-Key") or request.META.get("HTTP_X_API_KEY")
        if provided_api_key != required_api_key:
            irc_api_logger.warning(
                "login_token unauthorized ip=%s xff=%s username=%r api_key_present=%s",
                remote_ip,
                forwarded_for,
                request.data.get("username"),
                bool(provided_api_key),
            )
            return Response({"error": "Unauthorized"}, status=status.HTTP_200_OK)

    username = request.data.get("username")
    password = request.data.get("password")

    if not username or not password:
        irc_api_logger.warning(
            "login_token missing_fields ip=%s xff=%s username=%r password_present=%s",
            remote_ip,
            forwarded_for,
            username,
            bool(password),
        )
        return Response({"error": "Username and password are required."}, status=status.HTTP_200_OK)

    user = authenticate(username=username, password=password)
    if not user:
        UserModel = get_user_model()
        user_obj = UserModel.objects.filter(username=username).first()
        if user_obj:
            for app_pw in IrcAppPassword.objects.filter(user=user_obj, revoked_at__isnull=True).order_by("-created_at")[:10]:
                if check_password(password, app_pw.password):
                    user = user_obj
                    app_pw.last_used = timezone.now()
                    app_pw.save(update_fields=["last_used"])
                    break
    if not user or not getattr(user, "is_active", True) or not getattr(user, "email_verified", False):
        irc_api_logger.warning(
            "login_token invalid_credentials ip=%s xff=%s username=%r password_len=%s",
            remote_ip,
            forwarded_for,
            username,
            len(password) if isinstance(password, str) else None,
        )
        return Response({"error": "Invalid username or password."}, status=status.HTTP_200_OK)

    now = timezone.now()
    exp = now + timedelta(days=1)

    signing_key = getattr(settings, "EXTJWT_SECRET", None) or getattr(settings, "SECRET_KEY")
    issuer = getattr(settings, "JWT_ISSUER", "")

    payload = {
        "iss": issuer,
        "sub": user.username,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }

    token = jwt.encode(payload, signing_key, algorithm="HS256")
    if isinstance(token, bytes):
        token = token.decode("utf-8")

    return Response({"access_token": token, "email": getattr(user, "email", "") or ""}, status=status.HTTP_200_OK)


# Make ScopedRateThrottle apply the intended scope.
login_token.throttle_scope = "irc_api"


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def verify_email(request):
    """Verify an email address using a short code sent by email."""

    email = (request.data.get("email") or "").strip().lower()
    code = (request.data.get("code") or "").strip()

    if not email or not code:
        return Response({"error": "Email et code requis."}, status=status.HTTP_400_BAD_REQUEST)

    user = CustomUser.objects.filter(email__iexact=email).first()
    if not user:
        # Avoid leaking whether an email exists.
        return Response({"error": "Email ou code invalide."}, status=status.HTTP_400_BAD_REQUEST)

    ok, err = verify_email_code(user, code)
    if not ok:
        return Response({"error": err or "Email ou code invalide."}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"message": "Email confirmé. Vous pouvez vous connecter."}, status=status.HTTP_200_OK)


verify_email.throttle_scope = "verify_email"


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def resend_email_verification(request):
    email = (request.data.get("email") or "").strip().lower()
    if not email:
        return Response({"error": "Email requis."}, status=status.HTTP_400_BAD_REQUEST)

    user = CustomUser.objects.filter(email__iexact=email).first()
    if not user:
        # Avoid leaking whether an email exists.
        return Response({"message": "Si l'email existe, un code a été envoyé."}, status=status.HTTP_200_OK)
    if getattr(user, "email_verified", False):
        return Response({"message": "Si l'email existe, un code a été envoyé."}, status=status.HTTP_200_OK)

    try:
        issue_email_verification_code(user)
    except ValidationError:
        return Response({"message": "Veuillez patienter avant de demander un nouveau code."}, status=status.HTTP_429_TOO_MANY_REQUESTS)
    except Exception:
        return Response({"error": "Impossible d'envoyer l'email. Réessayez plus tard."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({"message": "Si l'email existe, un code a été envoyé."}, status=status.HTTP_200_OK)


resend_email_verification.throttle_scope = "resend_email"

# ✅ API Change Password (Requires Authentication)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    old_password = request.data.get("old_password")
    new_password = request.data.get("new_password")

    if not request.user.check_password(old_password):
        return Response({"error": "Incorrect old password"}, status=status.HTTP_400_BAD_REQUEST)

    request.user.set_password(new_password)
    request.user.save()

    return Response({"message": "Password changed successfully"}, status=status.HTTP_200_OK)

# ✅ API Change Email (Requires Authentication)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_email(request):
    new_email = request.data.get("new_email")

    UserModel = get_user_model()
    if UserModel.objects.filter(email=new_email).exists():
        return Response({"error": "Email already in use"}, status=status.HTTP_400_BAD_REQUEST)

    request.user.email = new_email
    request.user.save()

    return Response({"message": "Email updated successfully"}, status=status.HTTP_200_OK)

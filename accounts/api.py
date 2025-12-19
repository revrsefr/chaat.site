import json
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from rest_framework.decorators import api_view, permission_classes, authentication_classes, throttle_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import ScopedRateThrottle
from .utils import verify_recaptcha
from django.http import JsonResponse
from accounts.models import CustomUser
from accounts.tokens import get_tokens_for_user
from accounts.utils import verify_recaptcha
import traceback
import logging

from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import jwt

from accounts.models import IrcAppPassword
from accounts.utils import issue_email_verification_code, verify_email_code
from django.core.exceptions import ValidationError


irc_api_logger = logging.getLogger("accounts.irc_api")


@api_view(["POST"])
def register(request):
    try:
        if request.user.is_authenticated:
            return Response({"error": "You are already registered"}, status=status.HTTP_400_BAD_REQUEST)

        username = request.data.get("username")
        email = request.data.get("email")
        password1 = request.data.get("password1")
        password2 = request.data.get("password2")
        age = request.data.get("birthday")  # ✅ Fix age field (should be birthday)
        gender = request.data.get("gender")
        city = request.data.get("city")
        recaptcha_token = request.data.get("g_recaptcha_response") or request.data.get("g-recaptcha-response")
        avatar = request.FILES.get("avatar")  # ✅ Get uploaded avatar file

        # ✅ Debugging: Print received data (REMOVE in production)
        print("🔹 Received data:", request.data)

        # ✅ reCAPTCHA Verification
        is_valid, recaptcha_error = verify_recaptcha(recaptcha_token)
        if not is_valid:
            return Response({"error": f"reCAPTCHA failed: {recaptcha_error}"}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Check if username or email exists
        if CustomUser.objects.filter(username=username).exists():
            return Response({"error": "Username already exists"}, status=status.HTTP_400_BAD_REQUEST)
        if CustomUser.objects.filter(email=email).exists():
            return Response({"error": "Email already registered"}, status=status.HTTP_400_BAD_REQUEST)
        if password1 != password2:
            return Response({"error": "Passwords do not match"}, status=status.HTTP_400_BAD_REQUEST)
        if gender not in ["M", "F"]:
            return Response({"error": "Invalid gender"}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Create user
        user = CustomUser.objects.create(
            username=username,
            email=email,
            age=age,  # ✅ Make sure this is `birthday`
            gender=gender,
            city=city
        )
        user.set_password(password1)  # ✅ Hash password

        # New accounts must verify email before login.
        user.email_verified = False
        user.save()  # Ensure password + flags are persisted.

        # ✅ Save avatar AFTER user is created
        if avatar:
            user.avatar = avatar  
            user.save()  # ✅ Save the user with avatar

        # Email verification code
        try:
            issue_email_verification_code(user)
        except Exception:
            # Don't leak details in prod; keep server-side logs.
            return Response({
                "error": "Compte créé, mais impossible d'envoyer l'email de confirmation. Veuillez réessayer plus tard ou contacter le support.",
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            "message": "Compte créé. En attente de confirmation par email.",
            "requires_email_verification": True,
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        print("❌ ERROR in register API:", str(e))  # ✅ Print error
        print(traceback.format_exc())  # ✅ Show full traceback
        return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
def login_api(request):
    try:
        # ✅ Debugging: Print request data
        print("🔹 Received login data:", json.dumps(request.data, indent=4))

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

    except Exception as e:
        print(f"⚠️ API Error: {e}")
        return JsonResponse({"error": "Internal server error."}, status=500)


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
def verify_email(request):
    """Verify an email address using a short code sent by email."""

    email = (request.data.get("email") or "").strip().lower()
    code = (request.data.get("code") or "").strip()

    if not email or not code:
        return Response({"error": "Email et code requis."}, status=status.HTTP_400_BAD_REQUEST)

    user = CustomUser.objects.filter(email__iexact=email).first()
    if not user:
        return Response({"error": "Email inconnu."}, status=status.HTTP_400_BAD_REQUEST)

    ok, err = verify_email_code(user, code)
    if not ok:
        return Response({"error": err or "Code invalide."}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"message": "Email confirmé. Vous pouvez vous connecter."}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AllowAny])
def resend_email_verification(request):
    email = (request.data.get("email") or "").strip().lower()
    if not email:
        return Response({"error": "Email requis."}, status=status.HTTP_400_BAD_REQUEST)

    user = CustomUser.objects.filter(email__iexact=email).first()
    if not user:
        return Response({"error": "Email inconnu."}, status=status.HTTP_400_BAD_REQUEST)
    if getattr(user, "email_verified", False):
        return Response({"message": "Email déjà confirmé."}, status=status.HTTP_200_OK)

    try:
        issue_email_verification_code(user)
    except Exception:
        return Response({"error": "Impossible d'envoyer l'email. Réessayez plus tard."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({"message": "Nouveau code envoyé."}, status=status.HTTP_200_OK)

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

    if User.objects.filter(email=new_email).exists():
        return Response({"error": "Email already in use"}, status=status.HTTP_400_BAD_REQUEST)

    request.user.email = new_email
    request.user.save()

    return Response({"message": "Email updated successfully"}, status=status.HTTP_200_OK)

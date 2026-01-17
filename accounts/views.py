from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from rest_framework.request import Request
from django.contrib.auth import login, authenticate
from rest_framework.test import APIRequestFactory  # Creates API-like requests
from .api import register, login_api, change_password, change_email
from .models import CustomUser
from django.contrib.auth import get_user_model
from django.contrib.auth import logout
from .forms import ProfileUpdateForm
from django.http import JsonResponse
from django.utils import timezone
from django.contrib.auth.hashers import make_password
import secrets
from django.urls import reverse
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.template.loader import render_to_string
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.utils.http import url_has_allowed_host_and_scheme
from typing import Optional
from datetime import timedelta
from django.core.validators import EmailValidator
from django.utils.dateparse import parse_date
from django.core.cache import cache

from .models import IrcAppPassword
from .utils import issue_email_verification_code, verify_email_code

factory = APIRequestFactory()
CustomUser = get_user_model()

# ✅ Register View (Calls `register` API Directly)
def register_view(request):
    if request.method == "POST":
        api_request = factory.post("/accounts/api/register/", data=request.POST, files=request.FILES)
        api_request = Request(api_request)

        response = register(api_request)  # Call API function directly
        data = response.data

        if response.status_code == 201:
            messages.success(request, "Compte créé. Un code de confirmation a été envoyé à votre email.")
            return redirect("verify_email")
        else:
            messages.error(request, data.get("error", "An error occurred during registration."))

    return render(request, "accounts/register.html")

def login_view(request):
    wants_json = request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in (request.headers.get("accept") or "")

    def get_safe_next_url() -> Optional[str]:
        next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
        if not next_url:
            return None
        if url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return next_url
        return None

    if request.user.is_authenticated:
        next_url = get_safe_next_url()
        if wants_json:
            return JsonResponse({
                "ok": True,
                "redirect_url": next_url or reverse("profile", kwargs={"username": request.user.username}),
                "username": request.user.username,
            })
        return redirect(next_url or reverse("profile", kwargs={"username": request.user.username}))

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password")

        # ✅ Call the API Directly Without Wrapping `Request`
        api_request = factory.post("/accounts/api/login/", data={"username": username, "password": password})
        response = login_api(api_request)
        data = response.data

        if response.status_code == 200:
            resolved_username = data.get("username") or username

            # ✅ Get user manually (Since `authenticate()` fails with API passwords)
            try:
                user = CustomUser.objects.get(username=resolved_username)
                login(request, user)  # ✅ Use Django session login
                request.session["access_token"] = data["access_token"]
                request.session["refresh_token"] = data["refresh_token"]

                redirect_url = get_safe_next_url() or reverse("profile", kwargs={"username": user.username})
                if wants_json:
                    return JsonResponse({
                        "ok": True,
                        "redirect_url": redirect_url,
                        "username": user.username,
                        "message": "Login successful!",
                    })

                messages.success(request, "Login successful!")
                return redirect(redirect_url)  # ✅ Django Redirect (No JS)
            except CustomUser.DoesNotExist:
                if wants_json:
                    return JsonResponse({
                        "ok": False,
                        "error": {
                            "code": "unknown_user",
                            "message": "Nom d'utilisateur ou email inconnu.",
                        },
                        "field_errors": {"username": "Nom d'utilisateur ou email inconnu."},
                    }, status=400)
                messages.error(request, "User not found. Try registering.")

        error_message = data.get("error", "Invalid credentials.")
        error_code = data.get("code")
        field = data.get("field")
        field_errors = {}
        if error_code == "unknown_user" or field == "username":
            field_errors["username"] = error_message
        elif error_code == "bad_password" or field == "password":
            field_errors["password"] = error_message

        if wants_json:
            return JsonResponse({
                "ok": False,
                "error": {"code": error_code or "invalid_credentials", "message": error_message},
                "field_errors": field_errors,
            }, status=response.status_code if response.status_code else 400)

        messages.error(request, error_message)

    return render(request, "accounts/login.html")


def login_validate_view(request):
    """Preflight validation for the login form (AJAX).

    This is intentionally *format-only* (no account existence checks) to avoid
    enabling username/email enumeration.
    """

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": {"code": "method_not_allowed"}}, status=405)

    username = (request.POST.get("username") or "").strip()

    field_errors = {}
    if not username:
        field_errors["username"] = "Champ requis."
    else:
        if len(username) < 3:
            field_errors["username"] = "3 caractères minimum."
        elif " " in username:
            field_errors["username"] = "Évitez les espaces."
        elif "@" in username and "." not in username.split("@", 1)[-1]:
            field_errors["username"] = "Email invalide."

    return JsonResponse({"ok": True, "field_errors": field_errors})


def register_validate_view(request):
    """Preflight validation for the register form (AJAX).

    This is intentionally *format-only* (no account existence checks) to avoid
    enabling username/email enumeration.
    """

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": {"code": "method_not_allowed"}}, status=405)

    # Basic abuse protection: per-IP request limit.
    try:
        per_minute = int(getattr(settings, "REGISTER_PREFLIGHT_VALIDATE_PER_MINUTE", 30) or 0)
    except Exception:
        per_minute = 30
    if per_minute > 0:
        xff = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
        ip = xff or (request.META.get("REMOTE_ADDR") or "") or "unknown"
        rl_key = f"register_preflight_validate:{ip}"
        try:
            count = cache.incr(rl_key)
        except ValueError:
            cache.add(rl_key, 1, timeout=60)
            count = 1
        except Exception:
            count = 1
        if count > per_minute:
            return JsonResponse({"ok": False, "error": {"code": "rate_limited"}}, status=429)

    username = (request.POST.get("username") or "").strip()
    email = (request.POST.get("email") or "").strip().lower()
    password1 = request.POST.get("password1") or ""
    password2 = request.POST.get("password2") or ""
    birthday_raw = (request.POST.get("birthday") or "").strip()
    gender = (request.POST.get("gender") or "").strip()
    city = (request.POST.get("city") or "").strip()

    field_errors = {}

    if not username:
        field_errors["username"] = "Champ requis."
    else:
        try:
            CustomUser._meta.get_field("username").run_validators(username)
        except ValidationError:
            field_errors["username"] = "Nom d'utilisateur invalide."

    if not email:
        field_errors["email"] = "Champ requis."
    else:
        try:
            EmailValidator()(email)
        except ValidationError:
            field_errors["email"] = "Email invalide."

    if not password1:
        field_errors["password1"] = "Champ requis."
    else:
        try:
            validate_password(password1)
        except ValidationError as ve:
            # Avoid leaking too much detail; keep it user-friendly.
            field_errors["password1"] = ve.messages[0] if ve.messages else "Mot de passe trop faible."

    if not password2:
        field_errors["password2"] = "Champ requis."
    elif password1 and password1 != password2:
        field_errors["password2"] = "Les mots de passe ne correspondent pas."

    if birthday_raw:
        birthday = parse_date(birthday_raw)
        if not birthday:
            field_errors["birthday"] = "Date de naissance invalide."
    else:
        field_errors["birthday"] = "Champ requis."

    if gender not in ("M", "F"):
        field_errors["gender"] = "Veuillez sélectionner un genre."

    if not city:
        field_errors["city"] = "Champ requis."

    # Optional “pro” behavior: check whether username/email already exist.
    # WARNING: this enables enumeration; keep disabled unless you explicitly want it.
    if getattr(settings, "REGISTER_PREFLIGHT_CHECK_AVAILABILITY", False):
        if username and "username" not in field_errors:
            if CustomUser.objects.filter(username__iexact=username).exists():
                field_errors["username"] = "Ce pseudo est déjà pris."

        if email and "email" not in field_errors:
            if CustomUser.objects.filter(email__iexact=email).exists():
                field_errors["email"] = "Cet email est déjà utilisé."

    return JsonResponse({"ok": True, "field_errors": field_errors})

# ✅ Change Password (Uses `api_request`)
@login_required
def change_password_view(request):
    if request.method == "POST":
        api_request = factory.post("/accounts/api/change_password/", data=request.POST)
        api_request = Request(api_request)
        api_request.user = request.user  # Attach logged-in user to request

        response = change_password(api_request)
        data = response.data

        if response.status_code == 200:
            messages.success(request, "Password changed successfully!")
            return redirect("home")
        else:
            messages.error(request, data.get("error", "Failed to change password."))

    return render(request, "accounts/change_password.html")

# ✅ Change Email (Uses `api_request`)
@login_required
def change_email_view(request):
    if request.method == "POST":
        api_request = factory.post("/accounts/api/change_email/", data=request.POST)
        api_request = Request(api_request)
        api_request.user = request.user  # Attach logged-in user

        response = change_email(api_request)
        data = response.data

        if response.status_code == 200:
            messages.success(request, "Email updated successfully!")
            return redirect("home")
        else:
            messages.error(request, data.get("error", "Failed to update email."))

    return render(request, "accounts/change_email.html")

# ✅ Logout View (Clears JWT Tokens)
@login_required
def logout_view(request):
    # Clear any app-level tokens we stored in the session.
    request.session.pop("access_token", None)
    request.session.pop("refresh_token", None)

    # IMPORTANT: also end the Django authenticated session.
    logout(request)

    messages.success(request, "You have been logged out.")
    return redirect("login")

# ✅ Render Forgot Password Page
def forgot_password_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        user = CustomUser.objects.filter(email__iexact=email).first()
        if user:
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_url = request.build_absolute_uri(
                reverse("password_reset_confirm", kwargs={"uidb64": uid, "token": token})
            )
            subject = "Password Reset Request"
            message = render_to_string("accounts/password_reset_email.html", {"reset_url": reset_url, "user": user})
            send_mail(subject, message, None, [user.email])
            messages.success(request, "A password reset link has been sent to your email.")
        else:
            messages.error(request, "No user found with that email.")
        return redirect("forgot_password")
    return render(request, "accounts/forgot_password.html")


def password_reset_confirm_view(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = CustomUser.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
        user = None
    if user is not None and default_token_generator.check_token(user, token):
        if request.method == "POST":
            password1 = request.POST.get("new_password1")
            password2 = request.POST.get("new_password2")
            if password1 and password2 and password1 == password2:
                try:
                    validate_password(password1, user)
                    user.set_password(password1)
                    user.save()
                    messages.success(request, "Your password has been reset.")
                    return redirect("login")
                except ValidationError as e:
                    messages.error(request, ", ".join(e.messages))
            else:
                messages.error(request, "Passwords do not match.")
        return render(request, "accounts/password_reset_confirm.html", {"validlink": True})
    else:
        messages.error(request, "The password reset link is invalid or has expired.")
        return render(request, "accounts/password_reset_confirm.html", {"validlink": False})

def verify_email_view(request):
    """Renders the email verification page and validates codes."""

    if request.method == "POST":
        email = (request.POST.get("email") or "").strip()
        code = (request.POST.get("code") or "").strip()

        user = CustomUser.objects.filter(email__iexact=email).first()
        if not user:
            messages.error(request, "Email inconnu.", extra_tags="emailverify")
            return render(request, "accounts/verify_email.html", {"email": email})

        ok, err = verify_email_code(user, code)
        if not ok:
            messages.error(request, err or "Code invalide.", extra_tags="emailverify")
            return render(request, "accounts/verify_email.html", {"email": email})

        messages.success(request, "Email confirmé. Vous pouvez vous connecter.", extra_tags="emailverify")
        return redirect("login")

    email = (request.GET.get("email") or "").strip()
    return render(request, "accounts/verify_email.html", {"email": email})

@login_required
def profile_view(request, username):
    user_profile = get_object_or_404(CustomUser, username=username)

    wants_json = request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in (request.headers.get("accept") or "")

    # ✅ Restrict access: Only the owner can access & update their profile
    if request.user != user_profile:
        if wants_json:
            return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
        messages.error(request, "Vous n'avez pas la permission d'accéder à ce profil.")
        return redirect("home")  # Redirect unauthorized users

    if request.method == "GET" and wants_json:
        return JsonResponse({
            "ok": True,
            "profile": {
                "username": user_profile.username,
                "email": user_profile.email,
                "email_verified": bool(getattr(user_profile, "email_verified", False)),
                "age": user_profile.age.isoformat() if user_profile.age else None,
                "gender": user_profile.gender,
                "city": user_profile.city,
                "description": user_profile.description,
                "avatar_url": user_profile.avatar.url if user_profile.avatar else None,
            },
        })

    if request.method == "POST":
        form = ProfileUpdateForm(request.POST, request.FILES, instance=user_profile)
        if form.is_valid():
            form.save()
            if wants_json:
                user_profile.refresh_from_db()
                return JsonResponse({
                    "ok": True,
                    "message": "Votre profil a été mis à jour avec succès.",
                    "profile": {
                        "age": user_profile.age.isoformat() if user_profile.age else None,
                        "gender": user_profile.gender,
                        "city": user_profile.city,
                        "description": user_profile.description,
                        "avatar_url": user_profile.avatar.url if user_profile.avatar else None,
                    },
                })
            messages.success(request, "Votre profil a été mis à jour avec succès.")
            return redirect("profile", username=user_profile.username)
        if wants_json:
            return JsonResponse({"ok": False, "errors": form.errors.get_json_data()}, status=400)
    else:
        form = ProfileUpdateForm(instance=user_profile)

    irc_app_password_plain = request.session.pop("irc_app_password_plain", None)
    app_pw_ttl_seconds = getattr(settings, "IRC_APP_PASSWORD_TTL_SECONDS", 120)
    try:
        app_pw_ttl_seconds = int(app_pw_ttl_seconds)
    except Exception:
        app_pw_ttl_seconds = 120
    app_pw_ttl_seconds = min(max(app_pw_ttl_seconds, 10), 24 * 60 * 60)
    cutoff = timezone.now() - timedelta(seconds=app_pw_ttl_seconds)
    irc_app_password_count = IrcAppPassword.objects.filter(
        user=user_profile,
        revoked_at__isnull=True,
        last_used__isnull=True,
        created_at__gte=cutoff,
    ).count()

    return render(request, "accounts/profile.html", {
        "user_profile": user_profile,
        "form": form,
        "irc_app_password_plain": irc_app_password_plain,
        "irc_app_password_count": irc_app_password_count,
    })


@login_required
def generate_irc_app_password_view(request, username):
    user_profile = get_object_or_404(CustomUser, username=username)
    wants_json = request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in (request.headers.get("accept") or "")
    if request.user != user_profile:
        if wants_json:
            return JsonResponse({"error": "Forbidden"}, status=403)
        messages.error(request, "Vous n'avez pas la permission d'effectuer cette action.")
        return redirect("home")

    if request.method != "POST":
        if wants_json:
            return JsonResponse({"error": "Method not allowed"}, status=405)
        return redirect("profile", username=user_profile.username)

    # Revoke existing active tokens for simplicity (single active token).
    IrcAppPassword.objects.filter(user=user_profile, revoked_at__isnull=True).update(revoked_at=timezone.now())

    plain = secrets.token_urlsafe(24)
    IrcAppPassword.objects.create(user=user_profile, password=make_password(plain))
    if wants_json:
        resp = JsonResponse({"token": plain, "active": 1})
        resp["Cache-Control"] = "no-store, max-age=0"
        resp["Pragma"] = "no-cache"
        return resp

    request.session["irc_app_password_plain"] = plain
    messages.success(request, "Nouveau mot de passe IRC généré. Copiez-le maintenant (affiché une seule fois).")
    return redirect("profile", username=user_profile.username)


@login_required
def revoke_irc_app_password_view(request, username):
    user_profile = get_object_or_404(CustomUser, username=username)
    if request.user != user_profile:
        messages.error(request, "Vous n'avez pas la permission d'effectuer cette action.")
        return redirect("home")

    if request.method == "POST":
        IrcAppPassword.objects.filter(user=user_profile, revoked_at__isnull=True).update(revoked_at=timezone.now())
        wants_json = request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in (request.headers.get("accept") or "")
        if wants_json:
            return JsonResponse({"revoked": True, "active": 0})
        messages.success(request, "Mot de passe IRC révoqué.")

    return redirect("profile", username=user_profile.username)

@login_required
def account_settings_view(request):
    # Placeholder: redirect to profile until a dedicated settings page exists.
    return redirect("profile", username=request.user.username)

@login_required
def delete_account_view(request):
    if request.method == "POST":
        request.user.delete()  # ✅ Delete user
        logout(request)
        return redirect("home")  # ✅ Redirect to home after deleting

    return render(request, "accounts/profile.html")  # ✅ Make sure the template exists!

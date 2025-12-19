from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
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

from .models import IrcAppPassword

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
            messages.success(request, "Account created successfully! You can now log in.")
            return redirect("login")
        else:
            messages.error(request, data.get("error", "An error occurred during registration."))

    return render(request, "accounts/register.html")

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        # ✅ Call the API Directly Without Wrapping `Request`
        api_request = factory.post("/accounts/api/login/", data={"username": username, "password": password})
        response = login_api(api_request)
        data = response.data

        if response.status_code == 200:
            # ✅ Get user manually (Since `authenticate()` fails with API passwords)
            try:
                user = CustomUser.objects.get(username=username)
                login(request, user)  # ✅ Use Django session login
                request.session["access_token"] = data["access_token"]
                request.session["refresh_token"] = data["refresh_token"]

                messages.success(request, "Login successful!")
                return redirect("profile", username=user.username)  # ✅ Django Redirect (No JS)
            except CustomUser.DoesNotExist:
                messages.error(request, "User not found. Try registering.")

        messages.error(request, data.get("error", "Invalid credentials."))

    return render(request, "accounts/login.html")

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
    request.session.pop("access_token", None)
    request.session.pop("refresh_token", None)
    messages.success(request, "You have been logged out.")
    return redirect("login")

# ✅ Render Forgot Password Page
def forgot_password_view(request):
    return render(request, "accounts/forgot_password.html")

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
    irc_app_password_count = IrcAppPassword.objects.filter(user=user_profile, revoked_at__isnull=True).count()

    return render(request, "accounts/profile.html", {
        "user_profile": user_profile,
        "form": form,
        "irc_app_password_plain": irc_app_password_plain,
        "irc_app_password_count": irc_app_password_count,
    })


@login_required
def generate_irc_app_password_view(request, username):
    user_profile = get_object_or_404(CustomUser, username=username)
    if request.user != user_profile:
        messages.error(request, "Vous n'avez pas la permission d'effectuer cette action.")
        return redirect("home")

    if request.method != "POST":
        return redirect("profile", username=user_profile.username)

    # Revoke existing active tokens for simplicity (single active token).
    IrcAppPassword.objects.filter(user=user_profile, revoked_at__isnull=True).update(revoked_at=timezone.now())

    plain = secrets.token_urlsafe(24)
    IrcAppPassword.objects.create(user=user_profile, password=make_password(plain))

    wants_json = request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in (request.headers.get("accept") or "")
    if wants_json:
        return JsonResponse({"token": plain, "active": 1})

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
def account_settings_view(request, username):
    user_profile = get_object_or_404(CustomUser, username=username)
    if request.user != user_profile:
        messages.error(request, "Vous n'avez pas la permission d'accéder à ce profil.")
        return redirect("home")  # Redirect unauthorized users
    return render(request, "accounts/profile.html")

@login_required
def delete_account_view(request):
    if request.method == "POST":
        request.user.delete()  # ✅ Delete user
        logout(request)
        return redirect("home")  # ✅ Redirect to home after deleting

    return render(request, "accounts/profile.html")  # ✅ Make sure the template exists!

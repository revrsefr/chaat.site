from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory  # Creates API-like requests
from .api import register, login_api, change_password, change_email

factory = APIRequestFactory()  # Global request factory for API calls

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

# ✅ Login View (Uses `api_request`)
def login_view(request):
    if request.method == "POST":
        api_request = factory.post("/accounts/api/login/", data=request.POST)
        api_request = Request(api_request)

        response = login_api(api_request)  # Directly calls API function
        data = response.data

        if response.status_code == 200:
            request.session["access_token"] = data["access_token"]
            request.session["refresh_token"] = data["refresh_token"]
            messages.success(request, "Login successful!")
            return redirect("home")
        else:
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

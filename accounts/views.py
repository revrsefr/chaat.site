import asyncio
import json
import logging
from django.contrib.auth import login, logout
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.conf import settings
from django.contrib.auth import get_user_model
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from .authentication import authenticate_atheme
from .models import CustomUser
import requests

logger = logging.getLogger(__name__)
User = get_user_model()

ATHEME_JSONRPC_URL = "http://127.0.0.1:7001/jsonrpc"


### 🔹 LOGIN VIEW (ASYNC)
@csrf_exempt
async def login_view(request):
    if request.method == "POST":
        data = json.loads(request.body)
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return JsonResponse({"error": "Missing credentials"}, status=400)

        authcookie = await authenticate_atheme(username, password)

        if authcookie:
            user, created = await asyncio.to_thread(User.objects.get_or_create, username=username)
            user.authcookie = authcookie
            user.online = True
            await asyncio.to_thread(user.save)

            request.session["authcookie"] = authcookie
            request.session["account"] = username
            request.session.modified = True
            login(request, user)

            return JsonResponse({"success": "Login successful."})
        else:
            return JsonResponse({"error": "Invalid credentials"}, status=403)

    return render(request, "accounts/login.html")


### 🔹 LOGOUT VIEW
@login_required
async def logout_view(request):
    user = request.user
    user.online = False
    await asyncio.to_thread(user.save)

    request.session.flush()
    logout(request)
    return redirect("login")


### 🔹 PROFILE VIEW
@login_required
async def profile_view(request, username=None):
    """Render user profile page"""
    if username:
        user = await asyncio.to_thread(User.objects.filter, username=username)
        user = user.first() if user else None
        if not user:
            return JsonResponse({"error": "User not found"}, status=404)
    else:
        user = request.user  

    return render(request, "accounts/profile.html", {"user": user})


### 🔹 GET AVATAR API
async def get_avatar(request):
    """API Endpoint to return user avatar URL based on account name"""
    account = request.GET.get("account")

    if not account:
        return JsonResponse({"error": "Account parameter is required"}, status=400)

    try:
        user = await asyncio.to_thread(User.objects.get, username=account)
        avatar_url = request.build_absolute_uri(user.avatar.url) if user.avatar else None
        return JsonResponse({"avatar_url": avatar_url})
    except User.DoesNotExist:
        return JsonResponse({"avatar_url": None})


### 🔹 UPLOAD AVATAR
@login_required
@csrf_exempt
async def upload_avatar(request):
    if request.method == "POST" and request.FILES.get("avatar"):
        file = request.FILES["avatar"]
        valid_extensions = ['jpg', 'jpeg', 'png']
        ext = file.name.split('.')[-1].lower()

        if ext not in valid_extensions:
            return JsonResponse({"error": "Only JPEG and PNG files are allowed."}, status=400)

        user = request.user
        user.avatar = file
        await asyncio.to_thread(user.save)
        return redirect("profile")

    return JsonResponse({"error": "No file uploaded"}, status=400)


### 🔹 RESET PASSWORD (ASYNC)
@login_required
@csrf_exempt
async def reset_password_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method."}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format"}, status=400)

    new_password = data.get("new_password")
    if not new_password:
        return JsonResponse({"error": "⚠️ Missing new password."}, status=400)

    username = request.session.get("atheme_user")
    authcookie = request.session.get("authcookie")

    if not username or not authcookie:
        return JsonResponse({"error": "❌ You are not logged in."}, status=403)

    payload = {
        "method": "atheme.command",
        "params": [authcookie, username, ".", "NickServ", "SET", "PASSWORD", new_password],
        "id": "1"
    }

    try:
        response = await asyncio.to_thread(requests.post, ATHEME_JSONRPC_URL, json=payload, timeout=5)
        result = response.json()

        if response.status_code != 200 or "error" in result:
            error_message = result.get("error", {}).get("message", "Unknown error") if result else "No response from Atheme"
            return JsonResponse({"error": f"❌ {error_message}"}, status=400)

        return JsonResponse({"success": "✅ Password changed successfully."})

    except requests.exceptions.RequestException as e:
        return JsonResponse({"error": f"❌ Connection error: {str(e)}"}, status=500)


### 🔹 UPDATE PROFILE
@login_required
@csrf_exempt
async def update_profile(request):
    """Allow users to update ONLY their own profile"""
    if request.method == "POST":
        data = json.loads(request.body)
        age = data.get("age")
        gender = data.get("gender")

        if age:
            try:
                age = int(age)
                if age < 18 or age > 99:
                    return JsonResponse({"error": "Invalid age. Must be between 18 and 99."}, status=400)
            except ValueError:
                return JsonResponse({"error": "Invalid age format."}, status=400)

        if gender not in ["M", "F", ""]:
            return JsonResponse({"error": "Invalid gender selection."}, status=400)

        user = request.user
        user.age = age if age else None
        user.gender = gender if gender else None
        await asyncio.to_thread(user.save)

        return JsonResponse({"success": "Profile updated successfully."})

    return JsonResponse({"error": "Invalid request method."}, status=405)

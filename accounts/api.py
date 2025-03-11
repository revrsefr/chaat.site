import json
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .utils import verify_recaptcha
from django.http import JsonResponse
from accounts.models import CustomUser
from accounts.tokens import get_tokens_for_user
from accounts.utils import verify_recaptcha
import traceback


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
        recaptcha_token = request.data.get("g_recaptcha_response")
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

        # ✅ Save avatar AFTER user is created
        if avatar:
            user.avatar = avatar  
            user.save()  # ✅ Save the user with avatar

        tokens = get_tokens_for_user(user)
        return Response({
            "message": "Account created successfully!",
            "access_token": tokens["access"],
            "refresh_token": tokens["refresh"],
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

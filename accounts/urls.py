from django.urls import path
from .views import (
    login_view, logout_view, profile_view, get_avatar, upload_avatar,
    reset_password_api, update_profile
)

urlpatterns = [
    # Authentication
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),

    # Profile
    path("profile/", profile_view, name="profile"),
    path("profile/<str:username>/", profile_view, name="profile_by_username"),

    # Avatar Management
    path("upload-avatar/", upload_avatar, name="upload_avatar"),
    path("get-avatar/", get_avatar, name="get_avatar"),

    # Account Settings
    path("reset-password/", reset_password_api, name="reset_password"),
    path("update-profile/", update_profile, name="update_profile"),
]

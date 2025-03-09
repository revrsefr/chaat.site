from django.urls import path
from .views import (
    register_view, login_view, logout_view, forgot_password_view,
    change_password_view, change_email_view
)
from .api import register, login_api, change_password, change_email
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path("register/", register_view, name="register"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("forgot-password/", forgot_password_view, name="forgot_password"),
    path("change-password/", change_password_view, name="change_password"),
    path("change-email/", change_email_view, name="change_email"),

    # API Endpoints
    path("api/register/", register, name="api_register"),
    path("api/login/", login_api, name="api_login"),
    path("api/change-password/", change_password, name="api_change_password"),
    path("api/change-email/", change_email, name="api_change_email"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]

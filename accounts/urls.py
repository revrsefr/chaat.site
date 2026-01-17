from django.urls import path
from .views import (
    register_view, login_view, logout_view, forgot_password_view,
    change_password_view, change_email_view, profile_view,  account_settings_view,
    delete_account_view,
    login_validate_view,
    register_validate_view,
    verify_email_view,
    generate_irc_app_password_view,
    revoke_irc_app_password_view,
    password_reset_confirm_view, # <-- Added
)
from .api import register, login_api, login_token, change_password, change_email, verify_email, resend_email_verification
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path("register/", register_view, name="register"),
    path("register/validate/", register_validate_view, name="register_validate"),
    path("login/", login_view, name="login"),
    path("login/validate/", login_validate_view, name="login_validate"),
    path("logout/", logout_view, name="logout"),
    path("verify-email/", verify_email_view, name="verify_email"),
    path("forgot-password/", forgot_password_view, name="forgot_password"),
    path("reset/<uidb64>/<token>/", password_reset_confirm_view, name="password_reset_confirm"),
    path("change-password/", change_password_view, name="change_password"),
    path("change-email/", change_email_view, name="change_email"),
    path("profile/<str:username>/", profile_view, name="profile"),
    path("profile/<str:username>/irc-password/generate/", generate_irc_app_password_view, name="generate_irc_app_password"),
    path("profile/<str:username>/irc-password/revoke/", revoke_irc_app_password_view, name="revoke_irc_app_password"),
    path("settings/", account_settings_view, name="account_settings"),
    path("delete/", delete_account_view, name="delete_account"),
    

    # ✅ API Endpoints
    path("api/register/", register, name="api_register"),
    path("api/login/", login_api, name="api_login"),
    path("api/verify-email/", verify_email, name="api_verify_email"),
    path("api/resend-verify-email/", resend_email_verification, name="api_resend_verify_email"),
    path("api/login_token/", login_token, name="api_login_token"),
    path("api/change-password/", change_password, name="api_change_password"),
    path("api/change-email/", change_email, name="api_change_email"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]

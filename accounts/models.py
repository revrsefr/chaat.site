from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.html import format_html
from django.utils.timezone import now
from django.conf import settings

class CustomUser(AbstractUser):
    avatar = models.ImageField(upload_to="avatars/", default="avatars/default.jpg", blank=True, null=True)
    age = models.DateField(null=True, blank=True) 
    gender = models.CharField(max_length=1, choices=[("M", "Homme"), ("F", "Femme")], default="M")
    city = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    popularity_score = models.IntegerField(default=0)
    last_login = models.DateTimeField(default=now, null=False, blank=False)
    public = models.BooleanField(default=True)  

    # ✅ Fix conflicts with Django auth.User model
    groups = models.ManyToManyField(
        "auth.Group",
        related_name="customuser_set",
        blank=True,
        help_text="The groups this user belongs to.",
    )

    user_permissions = models.ManyToManyField(
        "auth.Permission",
        related_name="customuser_set",
        blank=True,
        help_text="Specific permissions for this user.",
    )

    def avatar_url(self):
        """Return a default avatar if the user hasn't uploaded one."""
        if self.avatar:
            return self.avatar.url
        return "/static/users/avatars/default-avatar.jpg"  # Default avatar path
    
    @property
    def avatar_tag(self):
            """Show avatar in Django Admin."""
            if self.avatar:
                return format_html('<img src="{}" style="width: 50px; height: 50px; border-radius: 50%;" />', self.avatar.url)
            return "No Avatar"

    avatar_tag.fget.short_description = "Avatar"  # ✅ Label for Admin Panel


class IrcAppPassword(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="irc_app_passwords")
    password = models.CharField(max_length=256)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "revoked_at"]),
        ]

    def __str__(self):
        return f"IRC app password for {self.user_id}"
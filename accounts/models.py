from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.html import format_html
from django.utils.timezone import now
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

import io

from PIL import Image, ImageOps

class CustomUser(AbstractUser):
    avatar = models.ImageField(upload_to="avatars/", default="avatars/default.jpg", blank=True, null=True)
    age = models.DateField(null=True, blank=True) 
    gender = models.CharField(max_length=1, choices=[("M", "Homme"), ("F", "Femme")], default="M")
    city = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    popularity_score = models.IntegerField(default=0)
    last_login = models.DateTimeField(default=now, null=False, blank=False)
    public = models.BooleanField(default=True)  

    # Email verification
    email_verified = models.BooleanField(default=False)
    email_verification_code_hash = models.CharField(max_length=256, blank=True, default="")
    email_verification_expires_at = models.DateTimeField(null=True, blank=True)
    email_verification_sent_at = models.DateTimeField(null=True, blank=True)

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
        default_static = "/static/images/default-avatar.svg"

        if not self.avatar or not getattr(self.avatar, "name", ""):
            return default_static

        try:
            # Be defensive: don't return a URL to a missing file.
            if hasattr(self.avatar, "storage") and hasattr(self.avatar.storage, "exists"):
                if not self.avatar.storage.exists(self.avatar.name):
                    return default_static
        except Exception:
            return default_static

        try:
            return self.avatar.url
        except Exception:
            return default_static

    def _avatar_thumb_storage_name(self, size: int) -> str:
        avatar_name = (getattr(self.avatar, "name", "") or "").strip()
        if not avatar_name:
            return ""

        base = avatar_name.rsplit(".", 1)[0]
        if base.startswith("avatars/"):
            base = base[len("avatars/"):]

        return f"avatars/thumbs/{base}__{size}.webp"

    def _generate_avatar_thumb(self, size: int) -> None:
        if not self.avatar or not getattr(self.avatar, "name", ""):
            return

        # Don't generate thumbs for the default placeholder.
        if self.avatar.name == "avatars/default.jpg":
            return

        thumb_name = self._avatar_thumb_storage_name(size)
        if not thumb_name:
            return

        if default_storage.exists(thumb_name):
            return

        # Ensure the original exists.
        if not default_storage.exists(self.avatar.name):
            return

        with default_storage.open(self.avatar.name, "rb") as fh:
            img = Image.open(fh)
            img = ImageOps.exif_transpose(img)

            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA")

            thumb = ImageOps.fit(img, (size, size), method=Image.Resampling.LANCZOS)

            buf = io.BytesIO()
            try:
                thumb.save(buf, format="WEBP", quality=78, method=6)
                content = ContentFile(buf.getvalue())
                default_storage.save(thumb_name, content)
            except Exception:
                # Fallback if WebP isn't available in the runtime.
                buf = io.BytesIO()
                if thumb.mode == "RGBA":
                    thumb = thumb.convert("RGB")
                thumb.save(buf, format="JPEG", quality=82, optimize=True, progressive=True)
                fallback_name = thumb_name[:-5] + ".jpg"
                default_storage.save(fallback_name, ContentFile(buf.getvalue()))

    def ensure_avatar_thumbs(self) -> None:
        # Sizes chosen to match common render sizes (100px avatars and ~261px cards).
        self._generate_avatar_thumb(100)
        self._generate_avatar_thumb(320)

    def avatar_thumb_100_url(self):
        default_static = "/static/images/default-avatar.svg"
        thumb = self._avatar_thumb_storage_name(100)
        if thumb and default_storage.exists(thumb):
            return default_storage.url(thumb)
        jpg = thumb[:-5] + ".jpg" if thumb else ""
        if jpg and default_storage.exists(jpg):
            return default_storage.url(jpg)
        return self.avatar_url() or default_static

    def avatar_thumb_320_url(self):
        default_static = "/static/images/default-avatar.svg"
        thumb = self._avatar_thumb_storage_name(320)
        if thumb and default_storage.exists(thumb):
            return default_storage.url(thumb)
        jpg = thumb[:-5] + ".jpg" if thumb else ""
        if jpg and default_storage.exists(jpg):
            return default_storage.url(jpg)
        return self.avatar_url() or default_static

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        try:
            self.ensure_avatar_thumbs()
        except Exception:
            # Never fail user saves due to thumbnail generation.
            pass
    
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
from django.db import models
from django.utils.text import slugify
from accounts.models import CustomUser 
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

import io

from PIL import Image, ImageOps

class BlogPost(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    content = models.TextField()
    image = models.ImageField(upload_to="blog_images/")
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE) 
    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    keywords = models.TextField(blank=True)  # Added for SEO
    category = models.CharField(max_length=255, blank=True)  # Added for categories
    tags = models.TextField(blank=True)  # Added for tags
    source_id = models.CharField(max_length=32, unique=True, blank=True, null=True)
    source_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    is_published = models.BooleanField(default=True)  # ✅ MUST EXIST

    class Meta:
        indexes = [
            models.Index(fields=["is_published", "created_at"], name="blogpost_pub_created_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)

        super().save(*args, **kwargs)

        try:
            self.ensure_image_thumbs()
        except Exception:
            # Never fail saving the post due to thumb generation.
            pass

    def _image_thumb_storage_name(self, size: int) -> str:
        image_name = (getattr(self.image, "name", "") or "").strip()
        if not image_name:
            return ""

        base = image_name.rsplit(".", 1)[0]
        if base.startswith("blog_images/"):
            base = base[len("blog_images/"):]

        return f"blog_images/thumbs/{base}__{size}.webp"

    def _generate_image_thumb(self, size: int) -> None:
        if not self.image or not getattr(self.image, "name", ""):
            return

        thumb_name = self._image_thumb_storage_name(size)
        if not thumb_name:
            return

        if default_storage.exists(thumb_name):
            return

        if not default_storage.exists(self.image.name):
            return

        with default_storage.open(self.image.name, "rb") as fh:
            img = Image.open(fh)
            img = ImageOps.exif_transpose(img)

            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA")

            # Most blog cards are square previews.
            thumb = ImageOps.fit(img, (size, size), method=Image.Resampling.LANCZOS)

            buf = io.BytesIO()
            try:
                thumb.save(buf, format="WEBP", quality=80, method=6)
                default_storage.save(thumb_name, ContentFile(buf.getvalue()))
            except Exception:
                buf = io.BytesIO()
                if thumb.mode == "RGBA":
                    thumb = thumb.convert("RGB")
                thumb.save(buf, format="JPEG", quality=84, optimize=True, progressive=True)
                fallback_name = thumb_name[:-5] + ".jpg"
                default_storage.save(fallback_name, ContentFile(buf.getvalue()))

    def ensure_image_thumbs(self) -> None:
        # Common sizes: ~326px cards (1x) and ~652px (2x).
        self._generate_image_thumb(326)
        self._generate_image_thumb(652)

    def image_thumb_326_url(self):
        thumb = self._image_thumb_storage_name(326)
        if thumb and default_storage.exists(thumb):
            return default_storage.url(thumb)
        jpg = thumb[:-5] + ".jpg" if thumb else ""
        if jpg and default_storage.exists(jpg):
            return default_storage.url(jpg)
        try:
            return self.image.url
        except Exception:
            return ""

    def image_thumb_652_url(self):
        thumb = self._image_thumb_storage_name(652)
        if thumb and default_storage.exists(thumb):
            return default_storage.url(thumb)
        jpg = thumb[:-5] + ".jpg" if thumb else ""
        if jpg and default_storage.exists(jpg):
            return default_storage.url(jpg)
        try:
            return self.image.url
        except Exception:
            return ""

    def __str__(self):
        return self.title

class Comment(models.Model):
    post = models.ForeignKey("BlogPost", on_delete=models.CASCADE, related_name="comments")
    name = models.CharField(max_length=100)
    email = models.EmailField()
    website = models.URLField(blank=True, null=True)
    content = models.TextField()  
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.name} on {self.post.title}"
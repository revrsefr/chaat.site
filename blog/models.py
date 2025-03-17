from django.db import models
from django.utils.text import slugify
from accounts.models import CustomUser 

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
    is_active = models.BooleanField(default=True)
    is_published = models.BooleanField(default=True)  # ✅ MUST EXIST

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

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
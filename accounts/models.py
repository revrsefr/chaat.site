from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
import asyncio

class CustomUserManager(BaseUserManager):
    async def create_user(self, username, authcookie=None, password=None):
        if not username:
            raise ValueError("Users must have a username")

        user = self.model(username=username, authcookie=authcookie)
        if password:
            user.set_password(password)
        await user.asave()
        return user

    async def create_superuser(self, username, password):
        user = await self.create_user(username, password=password)
        user.is_staff = True
        user.is_superuser = True
        await user.asave()
        return user

class CustomUser(AbstractUser):  # ✅ Fix: Keep AbstractUser to avoid admin errors
    username = models.CharField(max_length=150, unique=True)
    authcookie = models.CharField(max_length=64, blank=True, null=True)  # ✅ Ensure authcookie exists
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    age = models.PositiveIntegerField(blank=True, null=True)
    gender = models.CharField(max_length=1, choices=[("M", "Male"), ("F", "Female")], blank=True, null=True)
    online = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    # ✅ Fix group & permission conflicts
    groups = models.ManyToManyField(
        "auth.Group",
        related_name="customuser_groups",  # ✅ Prevent reverse accessor clash
        blank=True
    )
    user_permissions = models.ManyToManyField(
        "auth.Permission",
        related_name="customuser_permissions",  # ✅ Prevent reverse accessor clash
        blank=True
    )

    objects = CustomUserManager()

    def __str__(self):
        return self.username


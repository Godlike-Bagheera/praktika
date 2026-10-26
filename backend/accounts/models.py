import re

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models


username_validator = RegexValidator(
    regex=r"^[A-Za-z0-9_]{3,30}$",
    message="Только латиница, цифры и _, от 3 до 30 символов",
)


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, username, password, **extra_fields):
        if not email:
            raise ValueError("Email обязателен")
        if not username:
            raise ValueError("Имя пользователя обязательно")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, username=username, **extra_fields)
        if password:
            user.set_password(password)  # PBKDF2 hash, never plain text
        else:
            user.set_unusable_password()
        user.full_clean(exclude=["password"])
        user.save(using=self._db)
        return user

    def create_user(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.USER)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, username, password, **extra_fields)

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self._create_user(email, username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model with email login and role field."""

    class Role(models.TextChoices):
        USER = "user", "Пользователь"
        ADMIN = "admin", "Администратор"

    email = models.EmailField("email", max_length=254, unique=True, db_index=True)
    username = models.CharField(
        "имя пользователя",
        max_length=30,
        unique=True,
        validators=[username_validator],
    )
    role = models.CharField(
        "роль", max_length=10, choices=Role.choices, default=Role.USER
    )
    is_active = models.BooleanField("активен", default=True)
    is_staff = models.BooleanField("персонал", default=False)
    created_at = models.DateTimeField("дата регистрации", auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        verbose_name = "пользователь"
        verbose_name_plural = "пользователи"
        ordering = ["id"]

    def __str__(self):
        return self.username

    def save(self, *args, **kwargs):
        # Суперпользователь (созданный через createsuperuser) автоматически
        # получает роль admin, иначе фронтенд не покажет ему админские кнопки.
        if self.is_superuser:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN or self.is_superuser

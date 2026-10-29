from django.conf import settings
from django.core.validators import MaxLengthValidator
from django.db import models


class Category(models.Model):
    """Категория форума. Создаётся и редактируется только администратором."""

    name = models.CharField(
        "название", max_length=100, unique=True,
        error_messages={"unique": "Категория с таким названием уже существует"},
    )
    name_lower = models.CharField(
        "название (регистронезависимый ключ)", max_length=100,
        unique=True, editable=False, default="", blank=True,
    )
    created_at = models.DateTimeField("дата создания", auto_now_add=True)

    class Meta:
        verbose_name = "категория"
        verbose_name_plural = "категории"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        self.name_lower = (self.name or "").strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Topic(models.Model):
    """Тема форума, привязана к категории."""

    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="topics",
        verbose_name="категория",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="topics", verbose_name="автор",
    )
    title = models.CharField(
        "заголовок", max_length=120,
        validators=[MaxLengthValidator(120, message="Введите название темы (до 120 символов)")],
    )
    created_at = models.DateTimeField("дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("дата изменения", auto_now=True)

    class Meta:
        verbose_name = "тема"
        verbose_name_plural = "темы"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Post(models.Model):
    """Сообщение в теме."""

    topic = models.ForeignKey(
        Topic, on_delete=models.CASCADE, related_name="posts",
        verbose_name="тема",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="posts", verbose_name="автор",
    )
    text = models.TextField(
        "текст",
        validators=[MaxLengthValidator(2000, message="Введите сообщение (до 2000 символов)")],
    )
    created_at = models.DateTimeField("дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("дата изменения", auto_now=True)

    class Meta:
        verbose_name = "сообщение"
        verbose_name_plural = "сообщения"
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"Post {self.pk} in Topic {self.topic_id}"


class UserMention(models.Model):
    """Уведомление: в сообщении `post` упомянут пользователь `user` через @username."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="mentions", verbose_name="получатель",
    )
    post = models.ForeignKey(
        Post, on_delete=models.CASCADE,
        related_name="mention_notifications", verbose_name="сообщение",
    )
    read_at = models.DateTimeField("прочитано", null=True, blank=True)
    created_at = models.DateTimeField("дата", auto_now_add=True)

    class Meta:
        verbose_name = "упоминание"
        verbose_name_plural = "упоминания"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "post"], name="unique_mention_per_post",
            ),
        ]

    def __str__(self):
        return f"@{self.user_id} notified about post {self.post_id}"

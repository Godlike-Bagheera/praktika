from django.db import IntegrityError, transaction
from rest_framework import serializers

from .models import Category, Post, Topic
from .profanity import contains_profanity


def check_profanity(value: str) -> str:
    if contains_profanity(value, strict=True):
        raise serializers.ValidationError(
            "Сообщение содержит нецензурную лексику. Пожалуйста, воздержитесь от мата."
        )
    return value


class UserRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()


class CategorySerializer(serializers.ModelSerializer):
    topics_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Category
        fields = ["id", "name", "created_at", "topics_count"]
        read_only_fields = ["id", "created_at", "topics_count"]

    def validate_name(self, value):
        value = (value or "").strip()
        if not value or len(value) > 100:
            raise serializers.ValidationError(
                "Введите название категории (до 100 символов)"
            )
        qs = Category.objects.filter(name__iexact=value)
        if not qs.exists() and getattr(self, "instance", None) is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Эта категория уже существует")
        return value

    def save(self, **kwargs):
        try:
            with transaction.atomic():
                return super().save(**kwargs)
        except IntegrityError as exc:
            if "name_lower" not in str(exc):
                raise
            # Gunicorn с несколькими воркерами: уникальность в БД (name_lower) —
            # последний рубеж (проверка iexact выше не атомарна).
            raise serializers.ValidationError(
                {"name": "Эта категория уже существует"}
            )


class TopicSerializer(serializers.ModelSerializer):
    owner = UserRefSerializer(read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    posts_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Topic
        fields = [
            "id", "category", "category_name", "owner", "title",
            "posts_count", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "owner", "created_at", "updated_at",
                            "category_name", "posts_count"]

    def validate_title(self, value):
        value = (value or "").strip()
        if not value or len(value) > 120:
            raise serializers.ValidationError(
                "Введите название темы (до 120 символов)"
            )
        return check_profanity(value)

    def validate_category(self, value):
        if value is None:
            raise serializers.ValidationError("Выберите категорию")
        return value


class PostSerializer(serializers.ModelSerializer):
    owner = UserRefSerializer(read_only=True)
    topic_title = serializers.CharField(source="topic.title", read_only=True)

    class Meta:
        model = Post
        fields = [
            "id", "topic", "topic_title", "owner", "text",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "topic", "owner", "created_at",
                            "updated_at", "topic_title"]

    def validate_text(self, value):
        value = (value or "").strip()
        if not value or len(value) > 2000:
            raise serializers.ValidationError(
                "Введите сообщение (до 2000 символов)"
            )
        return check_profanity(value)


class TopicPatchSerializer(serializers.Serializer):
    """Частичное обновление темы (PUT /api/topics/:id) — только title."""

    title = serializers.CharField(max_length=120)

    def validate_title(self, value):
        value = (value or "").strip()
        if not value or len(value) > 120:
            raise serializers.ValidationError(
                "Введите название темы (до 120 символов)"
            )
        return check_profanity(value)


class PostPatchSerializer(serializers.Serializer):
    """Частичное обновление сообщения (PUT /api/posts/:id) — только text."""

    text = serializers.CharField(max_length=2000)

    def validate_text(self, value):
        value = (value or "").strip()
        if not value or len(value) > 2000:
            raise serializers.ValidationError(
                "Введите сообщение (до 2000 символов)"
            )
        return check_profanity(value)

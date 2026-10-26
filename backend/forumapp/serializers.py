from rest_framework import serializers

from .models import Category, Post, Topic


class UserRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "created_at"]
        read_only_fields = ["id", "created_at"]

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
            return super().save(**kwargs)
        except Exception as e:
            # Gunicorn с несколькими воркерами: уникальность в БД (name_lower) —
            # последний рубеж (проверка iexact выше не атомарна).
            from django.db import IntegrityError, transaction
            if isinstance(e, IntegrityError):
                transaction.rollback()
                raise serializers.ValidationError(
                    {"name": "Эта категория уже существует"}
                )
            raise


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
        return value

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
        return value

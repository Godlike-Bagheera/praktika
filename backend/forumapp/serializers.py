from django.db import IntegrityError, transaction
from rest_framework import serializers

from .models import Category, Post, PostReport, Topic
from .profanity import contains_profanity


class CategoryNameConflict(Exception):
    """Гонка при создании категории: name_lower уже занят другим запросом.

    View должен превратить это в 409 Conflict (а не 400/500).
    """


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
        # При редактировании (есть instance) исключаем саму категорию из
        # проверки — иначе переименование «Новости» -> «новости» или
        # сохранение своего имени давало бы ложный конфликт.
        instance = getattr(self, "instance", None)
        if instance is not None:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Эта категория уже существует")
        return value

    def save(self, **kwargs):
        # PostgreSQL (единственная поддерживаемая СУБД): name.save() приводит
        # имя к name_lower, поэтому unique-индекс по name_lower ловит и
        # точный дубль, и дубль в другом регистре.
        #   * обычная повторная вставка (не гонка) -> ValueError (view 400);
        #   * настоящая гонка (проверка iexact прошла, но INSERT упал по
        #     unique-индексу name_lower) -> CategoryNameConflict (view 409).
        creating = getattr(self, "instance", None) is None
        if creating and "name" in (self.validated_data or {}):
            # Неатомарная предварительная проверка: даёт понятный 400 для
            # обычного двойного клика; гонку дописывает блок ниже.
            if Category.objects.filter(
                    name__iexact=self.validated_data["name"]).exists():
                raise ValueError(
                    "Категория с таким названием уже существует"
                )
        try:
            with transaction.atomic():
                return super().save(**kwargs)
        except IntegrityError as exc:
            msg = str(exc)
            if creating and "name_lower" in msg:
                # Гонка при создании: несколько запросов/воркеров прошли
                # проверку iexact одновременно — пробрасываем сигнал,
                # чтобы view вернул 409 Conflict, а не маскировал гонку.
                raise CategoryNameConflict() from exc
            if "already exists" in msg.lower():
                raise ValueError(
                    "Категория с таким названием уже существует"
                ) from exc
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
            "created_at", "updated_at", "is_hidden",
        ]
        read_only_fields = ["id", "topic", "owner", "created_at",
                            "updated_at", "topic_title", "is_hidden"]

    def validate_text(self, value):
        value = (value or "").strip()
        if not value or len(value) > 2000:
            raise serializers.ValidationError(
                "Введите сообщение (до 2000 символов)"
            )
        return check_profanity(value)


class PostReportSerializer(serializers.ModelSerializer):
    post_title = serializers.CharField(source="post.topic.title", read_only=True)
    post_author = serializers.CharField(source="post.owner.username", read_only=True)
    reporter_username = serializers.CharField(source="user.username", read_only=True)
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = PostReport
        fields = [
            "id", "post", "post_title", "post_author", "reason",
            "reason_display", "status", "status_display", "created_at",
            "reporter_username",
        ]
        read_only_fields = [
            "status", "created_at", "reporter_username",
            "post_title", "post_author",
        ]

    def validate_post(self, value):
        user = self.context["request"].user
        if value.owner_id == user.id:
            raise serializers.ValidationError(
                "Нельзя пожаловаться на своё сообщение"
            )
        if PostReport.objects.filter(user=user, post=value).exists():
            raise serializers.ValidationError(
                "Вы уже жаловались на это сообщение"
            )
        return value


class PostReportCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostReport
        fields = ["post", "reason"]

    def validate_post(self, value):
        # Общая валидация с PostReportSerializer (свой пост / дубль жалобы).
        return PostReportSerializer.validate_post(self, value)

    def validate_reason(self, value):
        if value not in PostReport.Reason.values:
            raise serializers.ValidationError("Неизвестная причина жалобы")
        return value


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

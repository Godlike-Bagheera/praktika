import re

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from rest_framework import serializers

from .models import User

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")
PASSWORD_LETTER_DIGIT_RE = re.compile(r"(?=.*[A-Za-zА-Яа-я])(?=.*\d)")


class RegisterSerializer(serializers.Serializer):
    email = serializers.CharField(max_length=254)
    username = serializers.CharField(max_length=30)
    password = serializers.CharField(write_only=True, min_length=8, max_length=64)
    password_confirm = serializers.CharField(write_only=True)

    def validate_email(self, value):
        value = value.strip().lower()
        if not value:
            raise serializers.ValidationError("Введите корректный email")
        try:
            validate_email(value)
        except DjangoValidationError:
            raise serializers.ValidationError("Введите корректный email")
        if len(value) > 254:
            raise serializers.ValidationError("Введите корректный email")
        return value

    def validate_username(self, value):
        value = value.strip()
        if not USERNAME_RE.match(value):
            raise serializers.ValidationError(
                "Только латиница, цифры и _, от 3 до 30 символов"
            )
        return value

    def validate_password(self, value):
        if len(value) < 8 or len(value) > 64:
            raise serializers.ValidationError(
                "Пароль: от 8 символов, буквы и цифры"
            )
        if not PASSWORD_LETTER_DIGIT_RE.search(value):
            raise serializers.ValidationError(
                "Пароль: от 8 символов, буквы и цифры"
            )
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages[0])
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Пароли не совпадают"}
            )
        if User.objects.filter(email__iexact=attrs["email"]).exists():
            raise serializers.ValidationError({"email": "Этот email уже занят"})
        if User.objects.filter(username__iexact=attrs["username"]).exists():
            raise serializers.ValidationError(
                {"username": "Это имя пользователя уже занято"}
            )
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(
            email=validated_data["email"],
            username=validated_data["username"],
            password=validated_data["password"],
        )


class LoginSerializer(serializers.Serializer):
    email = serializers.CharField(max_length=254)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = (attrs.get("email") or "").strip().lower()
        password = attrs.get("password") or ""
        user = authenticate(username=email, password=password)
        if user is None or not user.is_active:
            # Единое сообщение: не раскрываем, что именно неверно
            raise serializers.ValidationError(
                {"detail": "Неверный email или пароль"}
            )
        attrs["user"] = user
        return attrs


class TopicPatchSerializer(serializers.Serializer):
    """Частичное обновление темы (PUT /api/topics/:id)."""

    title = serializers.CharField(required=False, allow_blank=True)

    def validate_title(self, value):
        value = (value or "").strip()
        if not value or len(value) > 120:
            raise serializers.ValidationError(
                "Введите название темы (до 120 символов)"
            )
        return value


class PostPatchSerializer(serializers.Serializer):
    """Частичное обновление сообщения (PUT /api/posts/:id)."""

    text = serializers.CharField(required=False, allow_blank=True)

    def validate_text(self, value):
        value = (value or "").strip()
        if not value or len(value) > 2000:
            raise serializers.ValidationError(
                "Введите сообщение (до 2000 символов)"
            )
        return value


class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "username", "role", "created_at"]
        read_only_fields = fields

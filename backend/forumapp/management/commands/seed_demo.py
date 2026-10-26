"""Создание администратора и демо-данных.

Использование:
    python manage.py seed_demo [--admin-email admin@example.com]
                               [--admin-username admin]
                               [--admin-password Admin12345]
"""
from django.core.management.base import BaseCommand

from accounts.models import User
from forumapp.models import Category, Post, Topic

DEFAULT_CATEGORIES = [
    "Общий раздел",
    "Программирование",
    "Помощь и вопросы",
    "Объявления",
]


class Command(BaseCommand):
    help = "Создаёт администратора, категории и демо-контент форума"

    def add_arguments(self, parser):
        parser.add_argument("--admin-email", default="admin@example.com")
        parser.add_argument("--admin-username", default="admin")
        parser.add_argument("--admin-password", default="Admin12345")

    def handle(self, *args, **options):
        email = options["admin_email"]
        username = options["admin_username"]
        password = options["admin_password"]

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            user = User.objects.create_superuser(
                email=email, username=username, password=password
            )
            self.stdout.write(self.style.SUCCESS(
                f"Создан администратор {email} / {password}"
            ))
        else:
            user.role = User.Role.ADMIN
            user.is_staff = True
            user.is_superuser = True
            user.save()
            self.stdout.write(f"Пользователь {email} уже существует, "
                              f"роль обновлена на admin")

        for name in DEFAULT_CATEGORIES:
            cat, created = Category.objects.get_or_create(name=name)
            if created:
                self.stdout.write(f"Категория: {name}")

        # Демо-пользователь и контент, если тем ещё нет
        if not Topic.objects.exists():
            demo, created = User.objects.get_or_create(
                email="user@example.com",
                defaults={"username": "demo"},
            )
            if created:
                demo.set_password("Demo12345")
                demo.save()
                self.stdout.write(self.style.SUCCESS(
                    "Создан демо-пользователь user@example.com / Demo12345"
                ))
            cat = Category.objects.first()
            topic = Topic.objects.create(category=cat, owner=demo,
                                         title="Добро пожаловать на форум!")
            Post.objects.create(topic=topic, owner=demo,
                                text="Это первое сообщение в теме.")
            Post.objects.create(topic=topic, owner=user,
                                text="Админ подтверждает: форум работает.")
            self.stdout.write(self.style.SUCCESS("Созданы демо-тема и сообщения"))

# Test settings: PostgreSQL only (as in production). SQLite is NOT used.
import os

# Тестовый SECRET_KEY должен попасть в окружение ДО импорта forum.settings:
# при DEBUG=False без DJANGO_SECRET_KEY настройки падают с ValueError
# (фикс безопасности) — здесь эмулируется корректно настроенный production.
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key-only-not-for-production")

from forum.settings import *  # noqa

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]  # noqa

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("TEST_DB_NAME", "forumdb"),  # noqa
        "USER": os.environ.get("DB_USER", "forumuser"),  # noqa
        "PASSWORD": os.environ.get("DB_PASSWORD", "testpass"),  # noqa
        "HOST": os.environ.get("DB_HOST", "localhost"),  # noqa
        "PORT": os.environ.get("DB_PORT", "5432"),  # noqa
        "TEST": {"NAME": os.environ.get("TEST_DB_NAME", "test_forumdb")},  # noqa
    }
}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.PBKDF2PasswordHasher"]
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

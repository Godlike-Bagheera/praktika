# Test settings: PostgreSQL only (as in production). SQLite is NOT used.
from forum.settings import *  # noqa

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

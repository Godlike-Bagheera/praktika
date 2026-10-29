"""
Django settings for the Forum project.
"""
import logging
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

logger = logging.getLogger(__name__)

# Load .env if python-dotenv is available (local development convenience)
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass


def env_bool(name, default=False):
    val = os.environ.get(name)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")


# --------------------------------------------------------------------------
# Core settings
# --------------------------------------------------------------------------
DEBUG = env_bool("DJANGO_DEBUG", False)

# SECRET_KEY: в production (DEBUG=False) без DJANGO_SECRET_KEY сервер НЕ
# запускается — хардкод-фоллбэк недопустим. В DEBUG mode dev-ключ остаётся,
# но с явным предупреждением в логе.
_dev_key_warning = None
_secret_from_env = os.environ.get("DJANGO_SECRET_KEY")
if _secret_from_env:
    SECRET_KEY = _secret_from_env
elif DEBUG:
    SECRET_KEY = "django-insecure-dev-only-0123456789abcdef"
    _dev_key_warning = (
        "Используется DEV SECRET_KEY (DJANGO_SECRET_KEY не задан). "
        "НИКОГДА не запускайте так production: задайте DJANGO_SECRET_KEY."
    )
else:
    raise ValueError(
        "DJANGO_SECRET_KEY не задан при DEBUG=False. Задайте надёжный "
        "секретный ключ в окружении или файле .env, например: "
        "DJANGO_SECRET_KEY=$(python -c \"from django.core.management.utils "
        "import get_random_secret_key; print(get_random_secret_key())\")"
    )

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get(
        "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,app,nginx"
    ).split(",")
    if h.strip()
]

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
    if o.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    # local
    "accounts",
    "forumapp",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # JWT из httpOnly-кук (подставляет Authorization заголовок для DRF)
    "forum.middleware.JwtCookieAuthMiddleware",
]

ROOT_URLCONF = "forum.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "forum.wsgi.application"

# --------------------------------------------------------------------------
# Database: PostgreSQL 16 (SQLite is NOT used anywhere, including tests)
# --------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "forumdb"),
        "USER": os.environ.get("DB_USER", "forumuser"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "changeme"),
        "HOST": os.environ.get("DB_HOST", "db"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}

# --------------------------------------------------------------------------
# Auth / user model
# --------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation."
                "UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation."
                "MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {
        "NAME": "django.contrib.auth.password_validation."
                "CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation."
                "NumericPasswordValidator",
    },
]

# --------------------------------------------------------------------------
# Internationalization
# --------------------------------------------------------------------------
LANGUAGE_CODE = "ru"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# Django admin login page language: keep English UI for admins
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# REST framework + JWT
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "UNAUTHENTICATED_USER": None,
    "EXCEPTION_HANDLER": "forum.exceptions.api_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=24),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# --------------------------------------------------------------------------
# CORS (for local development; nginx proxies API in production)
# --------------------------------------------------------------------------
# В production (DEBUG=False) CORS_ALLOW_ALL_ORIGINS жёстко False: любой сайт
# не сможет слать запросы к API с чужого домена. Если администратор всё же
# выставил CORS_ALLOW_ALL=true при DEBUG=False — это ошибка конфигурации:
# выводим предупреждение в лог при старте Django (сервер НЕ падает), а
# wildcard по-прежнему игнорируется. Для внешних фронтендов используйте
# whitelist CORS_ALLOWED_ORIGINS (через запятую, пример в .env.example).
CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL", DEBUG) and DEBUG

if not DEBUG and env_bool("CORS_ALLOW_ALL", False):
    import warnings
    warnings.warn(
        "CORS_ALLOW_ALL=true проигнорирован в production (DEBUG=False): "
        "CORS_ALLOW_ALL_ORIGINS оставлен False. Перечислите свои домены "
        "через CORS_ALLOWED_ORIGINS.",
        RuntimeWarning,
        stacklevel=1,
    )

CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
    if o.strip()
]

# --------------------------------------------------------------------------
# Cache (used by django-ratelimit) and sessions
# --------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "forum-cache",
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.db"

RATELIMIT_USE_CACHE = "default"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

# Предупреждения о небезопасной конфигурации — после настройки логгера,
# чтобы администратор заметил их в логе при старте Django.
if _dev_key_warning:
    logger.warning(_dev_key_warning)

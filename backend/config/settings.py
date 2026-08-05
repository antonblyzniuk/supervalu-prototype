"""Django settings for the SuperValu internal tooling backend.

Configuration is environment-driven (see `.env.example` at the repo root).
"""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:5173"]),
    CSRF_TRUSTED_ORIGINS=(list, ["http://localhost:5173"]),
)

# Read a local .env when present (docker-compose injects env vars directly).
env_file = BASE_DIR.parent / ".env"
if env_file.exists():
    env.read_env(env_file)

SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-dev-key-change-me")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

# Railway injects the service's public domain. Trusting it automatically means
# a deploy works without hand-copying the generated hostname into two settings.
RAILWAY_PUBLIC_DOMAIN = env("RAILWAY_PUBLIC_DOMAIN", default="")
RAILWAY_PRIVATE_DOMAIN = env("RAILWAY_PRIVATE_DOMAIN", default="")
for _domain in (RAILWAY_PUBLIC_DOMAIN, RAILWAY_PRIVATE_DOMAIN):
    if _domain and _domain not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_domain)

# --------------------------------------------------------------------------
# Applications
# --------------------------------------------------------------------------

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
]

LOCAL_APPS = [
    "apps.accounts",
    "apps.core",
    "apps.stores",
    "apps.dockets",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://supervalu:supervalu@localhost:5432/supervalu",
    )
}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DATABASE_CONN_MAX_AGE", default=60)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------
# Internationalization
# --------------------------------------------------------------------------

LANGUAGE_CODE = "en-ie"
TIME_ZONE = env("DJANGO_TIME_ZONE", default="Europe/Dublin")
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
# Static / media
# --------------------------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Signatures and docket photos. On Railway this MUST point at a mounted volume
# (RAILWAY_VOLUME_MOUNT_PATH) — the container filesystem is wiped on redeploy.
MEDIA_URL = env("DJANGO_MEDIA_URL", default="/media/")
MEDIA_ROOT = env("DJANGO_MEDIA_ROOT", default=str(BASE_DIR / "media"))

# Django only serves MEDIA_URL itself when DEBUG is on, and WhiteNoise covers
# static files only — so without this, every signature and photo 404s in
# production. Serving through gunicorn is fine at three-store scale; move to
# object storage (S3/R2) before this carries real traffic.
SERVE_MEDIA_FILES = env.bool("DJANGO_SERVE_MEDIA", default=True)

# --------------------------------------------------------------------------
# DRF
# --------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.DefaultPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("JWT_ACCESS_MINUTES", default=30)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("JWT_REFRESH_DAYS", default=7)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "SuperValu Tools API",
    "DESCRIPTION": "Internal tooling for SuperValu store staff and management.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/api/",
}

# --------------------------------------------------------------------------
# CORS / CSRF
# --------------------------------------------------------------------------

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True

if RAILWAY_PUBLIC_DOMAIN:
    _self_origin = f"https://{RAILWAY_PUBLIC_DOMAIN}"
    if _self_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_self_origin)

# --------------------------------------------------------------------------
# Security (tightened automatically when DEBUG is off)
# --------------------------------------------------------------------------

if not DEBUG:
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", default="INFO")},
    "loggers": {
        "django.db.backends": {"level": "INFO", "handlers": ["console"], "propagate": False},
    },
}

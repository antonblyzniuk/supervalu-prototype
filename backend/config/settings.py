"""Django settings for the SuperValu internal tooling backend.

Configuration is environment-driven (see `.env.example` at the repo root).
"""

from datetime import timedelta
from decimal import Decimal
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
ON_RAILWAY = bool(RAILWAY_PUBLIC_DOMAIN or RAILWAY_PRIVATE_DOMAIN)

_railway_hosts = [RAILWAY_PUBLIC_DOMAIN, RAILWAY_PRIVATE_DOMAIN]
if ON_RAILWAY:
    # Railway's platform health check reaches the container directly and sends
    # its own Host header, so it must be allowed or every probe 400s and the
    # deploy never goes healthy.
    _railway_hosts.append("healthcheck.railway.app")
    # Once a custom domain is attached, RAILWAY_PUBLIC_DOMAIN becomes that
    # domain and the generated *.up.railway.app address stops being trusted —
    # which breaks service-to-service calls that deliberately bypass the CDN.
    # The namespace is Railway-controlled, so trusting it is safe.
    _railway_hosts.extend([".up.railway.app", ".railway.internal"])

for _domain in _railway_hosts:
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
    "apps.departments",
    "apps.dockets",
    "apps.rosters",
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

# Shared code that lets someone create an admin account through
# /api/auth/bootstrap-admin/. Leave it unset and the endpoint is disabled —
# which is what it should be once the first admin exists.
ADMIN_BOOTSTRAP_CODE = env("ADMIN_BOOTSTRAP_CODE", default="")

# National minimum wage, in euro per hour. Used as the rate for anyone an admin
# has not given an explicit one, and as the floor that a rate is validated
# against — raise it when the statutory rate changes.
MINIMUM_HOURLY_RATE = Decimal(env("MINIMUM_HOURLY_RATE", default="14.20"))

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

# A docket is posted as one JSON document with its signatures and photos inline
# as base64, so the request body is far bigger than a plain form. Django's
# 2.5 MB default rejected a docket with a few photos before any view ran.
DATA_UPLOAD_MAX_MEMORY_SIZE = env.int("DJANGO_DATA_UPLOAD_MAX", default=32 * 1024 * 1024)
FILE_UPLOAD_MAX_MEMORY_SIZE = env.int("DJANGO_FILE_UPLOAD_MAX", default=16 * 1024 * 1024)
# Each line is an object with ~14 keys; 200 lines plus photos stays well under.
DATA_UPLOAD_MAX_NUMBER_FIELDS = env.int("DJANGO_DATA_UPLOAD_MAX_FIELDS", default=10_000)

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
    # Only applies to views that set `throttle_scope`.
    "DEFAULT_THROTTLE_CLASSES": ("rest_framework.throttling.ScopedRateThrottle",),
    "DEFAULT_THROTTLE_RATES": {
        # Guards the shared-code endpoint against brute force. Counted in the
        # local-memory cache, so it is per gunicorn worker — a speed bump, not
        # a wall. The code itself needs to be long and random.
        "admin_bootstrap": env("ADMIN_BOOTSTRAP_RATE", default="5/hour"),
    },
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
    # The platform probe hits the container over plain http with no
    # X-Forwarded-Proto, so without this it gets a 301 and never sees a 200.
    SECURE_REDIRECT_EXEMPT = [r"^api/health/$"]
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

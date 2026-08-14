import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Core Django ---
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'dev-only-insecure-key-change-in-production')
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'upload',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================================================
# Upload / scan pipeline settings
# =============================================================

AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME', 'your-bucket-name')

MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024 * 1024  # 5GB

ALLOWED_MIME_TYPES = [
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]

# --- ClamAV ---
# 'unix'    -> local clamd socket (dev / single-host deployments)
# 'network' -> clamd running as a separate service (containers, ECS, etc.)
CLAMAV_MODE = os.environ.get('CLAMAV_MODE', 'unix')
CLAMAV_HOST = os.environ.get('CLAMAV_HOST', 'clamav')
CLAMAV_PORT = int(os.environ.get('CLAMAV_PORT', 3310))

# --- Celery ---
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_SOFT_TIME_LIMIT = 240
CELERY_WORKER_MAX_TASKS_PER_CHILD = 100

CELERY_BEAT_SCHEDULE = {
    "reconcile-stuck-uploads": {
        "task": "upload.tasks.reconcile_stuck_uploads",
        "schedule": 600.0,  # every 10 minutes
    },
}

# --- DRF ---
REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.UserRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "user": "100/hour",
        "uploads": "20/hour",
    },
}

# --- Logging ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "upload": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "celery": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

# --- CORS ---
# For real browser-based uploads, install django-cors-headers:
#   pip install django-cors-headers
# add 'corsheaders' to INSTALLED_APPS and
# 'corsheaders.middleware.CorsMiddleware' near the top of MIDDLEWARE, then:
# CORS_ALLOWED_ORIGINS = ["https://your-frontend-domain.com"]
#
# Your S3 bucket also needs its own separate CORS policy — see PLAN.md.

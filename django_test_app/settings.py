import os
import tempfile

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(tempfile.gettempdir(), "db.sqlite3"),
    }
}

SECRET_KEY = "secret"

INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.admin",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.sessions",
    "ixp_tracker",
)

MIDDLEWARE = (
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
)

AUTHENTICATION_BACKENDS = ("django.contrib.auth.backends.ModelBackend",)

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": (
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
            ),
        },
    },
]

DEBUG = True

IXP_TRACKER_PEERING_DB_URL = "https://www.peeringdb.com/api"
IXP_TRACKER_PEERING_DB_KEY = "foobar"

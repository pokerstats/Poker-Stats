"""
Django settings for pokerstats project.

Generated by 'django-admin startproject' using Django 3.2.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.2/ref/settings/
"""

from pathlib import Path
import os
import environ

# Initialise environment variables
env = environ.Env()
environ.Env.read_env()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
if os.environ.get('GITHUB_WORKFLOW'):
    DEBUG = True
else:
    DEBUG = env('DEBUG') == 'True'

ALLOWED_HOSTS = ['pokerstats.lol', 'www.pokerstats.lol', '67.205.147.15', 'localhost']

# Application definition

INSTALLED_APPS = [
    # My apps
    'root',
    'tournament',
    'tournament_analytics',
    'tournament_group',
    'user',

    # Third party apps
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'bootstrap5',
    'crispy_forms',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.humanize',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'storages',
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

ROOT_URLCONF = 'pokerstats.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'root.context_processors.app_name',
                'root.context_processors.domain'
            ],
        },
    },
]

WSGI_APPLICATION = 'pokerstats.wsgi.application'


# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': env('DB_NAME'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

if os.environ.get('GITHUB_WORKFLOW'):
    DATABASES = {
        'default': {
           'ENGINE': 'django.db.backends.postgresql_psycopg2',
           'NAME': 'github_actions',
           'USER': 'postgres',
           'PASSWORD': 'postgres',
           'HOST': '127.0.0.1',
           'PORT': '5432',
        }
    }

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend'
]

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'APP': {
            'client_id': env('GOOGLE_AUTH_CLIENT_ID'),
            'secret': env('GOOGLE_AUTH_CLIENT_SECRET'),
            'key': ''
        }
    }
}


AUTH_USER_MODEL = 'user.User'
ACCOUNT_USER_MODEL_USERNAME_FIELD = 'username'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = True
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_SIGNUP_PASSWORD_ENTER_TWICE = True
ACCOUNT_SIGNUP_EMAIL_ENTER_TWICE = True
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_EMAIL_CONFIRMATION_COOLDOWN=1
ACCOUNT_LOGIN_ON_PASSWORD_RESET=True
LOGIN_URL = 'account_login'
LOGOUT_REDIRECT_URL = 'home'
LOGIN_REDIRECT_URL = 'home'
ACCOUNT_EMAIL_SUBJECT_PREFIX = '(pokerstats.lol) '

SITE_ID = 1


# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Email configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env('EMAIL_ID')
EMAIL_HOST_PASSWORD = env('EMAIL_PASSWORD')

DEFAULT_FROM_EMAIL = 'noreply<verify@tabian.ca>'

# Internationalization
# https://docs.djangoproject.com/en/3.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'US/Pacific'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/
if DEBUG == False:
    AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_ENDPOINT_URL = env('AWS_S3_ENDPOINT_URL')
    AWS_S3_OBJECT_PARAMETERS = {
        'CacheControl': 'max-age=86400',
        'ACL': 'public-read',
    }
    AWS_LOCATION = env('AWS_LOCATION')

    STATICFILES_DIRS = [
        os.path.join(BASE_DIR, 'static'),
    ]
    STATIC_URL = 'https://%s/%s/' % (AWS_S3_ENDPOINT_URL, AWS_LOCATION)
    STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
else:
    STATICFILES_DIRS = [
        BASE_DIR / "static",
    ]
    STATIC_ROOT = "static_cdn"

    STATIC_URL = '/static/'

    MEDIA_URL = '/media/'

    MEDIA_ROOT = 'media_cdn'


# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'












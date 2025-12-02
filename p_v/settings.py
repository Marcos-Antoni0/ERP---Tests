from pathlib import Path
import dj_database_url
import os


BASE_DIR = Path(__file__).resolve().parent.parent


SECRET_KEY = 'django-insecure-@90(9sd95!tqa*2xj%u&_!nq9oku7mav%66@4o6k@z8nh(*1$w'


DEBUG = True

ALLOWED_HOSTS = [
    'mult-tenent-system-production.up.railway.app',
    'erpforttech.up.railway.app',
    'localhost',
    '127.0.0.1',
    # Ou para aceitar qualquer domínio (menos seguro):
    # '*'
]


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'p_v_App',
    'accounts',
    'core',
    'catalog',
    'sales',
    'orders',
    'inventory',
    'tables',
    'staff',
    'clients',
    'debts',
    'django.contrib.humanize',

]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'p_v_App.middleware.SingleSessionMiddleware',  # Middleware de sessão única
    'p_v_App.middleware_tenant.TenantMiddleware',  # Middleware de multi-tenancy
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'p_v.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
        ],
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

WSGI_APPLICATION = 'p_v.wsgi.application'


DATABASES = {
    'default': dj_database_url.config(
        default='postgresql://postgres:BnjhNMbyYUgvRUHzdRTISmYicWdkRTLh@trolley.proxy.rlwy.net:46402/railway',
        conn_max_age=600,
        ssl_require=not DEBUG
    )
}


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


LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = True

CSRF_TRUSTED_ORIGINS = [
    'https://web-production-05c6b.up.railway.app',
    'https://8000-iiq7h8kg72desdjs2n7v4-3b10558d.manus.computer',
    'https://mult-tenent-system-production.up.railway.app',
    'https://erpforttech.up.railway.app',
]

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = (

    './static',
)
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_REDIRECT_URL = '/'
LOGIN_URL = '/login/'

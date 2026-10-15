import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-only-change-me')
DEBUG = os.getenv('DJANGO_DEBUG', '1') == '1'
ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip()]

INSTALLED_APPS = ['django.contrib.contenttypes', 'django.contrib.auth', 'corsheaders', 'routing']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'corsheaders.middleware.CorsMiddleware', 'django.middleware.common.CommonMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = []
WSGI_APPLICATION = 'config.wsgi.application'
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

ROUTING_PROVIDER = os.getenv('ROUTING_PROVIDER', 'osrm').lower()
MAPBOX_ACCESS_TOKEN = os.getenv('MAPBOX_ACCESS_TOKEN', '')
OSRM_BASE_URL = os.getenv('OSRM_BASE_URL', 'https://router.project-osrm.org')
NOMINATIM_URL = os.getenv('NOMINATIM_URL', 'https://nominatim.openstreetmap.org')
OPEN_METEO_URL = os.getenv('OPEN_METEO_URL', 'https://api.open-meteo.com/v1/forecast')
APP_USER_AGENT = os.getenv('APP_USER_AGENT', 'WeatherAwareTruckRouting/1.0 (assessment demo)')

CORS_ALLOWED_ORIGINS = [x.strip() for x in os.getenv('CORS_ALLOWED_ORIGINS', '').split(',') if x.strip()]

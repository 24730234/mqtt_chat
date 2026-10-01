"""Local integration settings for the real Django/MySQL/Mosquitto stack."""
import os
from config.settings import *  # noqa: F403

DATABASES = {"default": {
    "ENGINE": "django.db.backends.mysql",
    "NAME": "mqtt_chat",
    "USER": "mqtt_chat",
    "PASSWORD": os.environ["MYSQL_PASSWORD"],
    "HOST": "db",
    "PORT": "3306",
    "OPTIONS": {"charset": "utf8mb4"},
}}
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "web", "testserver"]
MEDIA_ROOT = "/media"
LOGGING = {
    "version": 1, "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

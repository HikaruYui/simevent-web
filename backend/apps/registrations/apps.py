# Fungsi file: Registrasi AppConfig Django untuk app registrations.

from django.apps import AppConfig


class RegistrationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.registrations"

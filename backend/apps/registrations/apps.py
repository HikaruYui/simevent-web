# Fungsi file: Registrasi AppConfig Django untuk app registrations.

from django.apps import AppConfig


# Inheritance: RegistrationsConfig mewarisi mekanisme konfigurasi aplikasi Django.
class RegistrationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.registrations"

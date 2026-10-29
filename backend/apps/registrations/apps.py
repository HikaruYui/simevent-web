# Fungsi file: Registrasi AppConfig Django untuk app registrations.

from django.apps import AppConfig


# Inheritance: RegistrationsConfig mewarisi mekanisme konfigurasi aplikasi Django.
# OOP — Hierarchical inheritance: AppConfig juga menjadi induk class saudara lain di proyek.
class RegistrationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.registrations"

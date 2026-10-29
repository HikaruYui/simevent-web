# Fungsi file: Registrasi AppConfig Django untuk app partnerships.

from django.apps import AppConfig


# Inheritance: PartnershipsConfig mewarisi mekanisme konfigurasi aplikasi Django.
# OOP — Hierarchical inheritance: AppConfig juga menjadi induk class saudara lain di proyek.
class PartnershipsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.partnerships"

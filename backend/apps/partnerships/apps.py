# Fungsi file: Registrasi AppConfig Django untuk app partnerships.

from django.apps import AppConfig


# Inheritance: PartnershipsConfig mewarisi mekanisme konfigurasi aplikasi Django.
class PartnershipsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.partnerships"

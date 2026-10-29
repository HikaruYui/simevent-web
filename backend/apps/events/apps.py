# Fungsi file: Registrasi AppConfig Django untuk app events.

from django.apps import AppConfig


# Inheritance: EventsConfig mewarisi mekanisme konfigurasi aplikasi Django.
# OOP — Hierarchical inheritance: AppConfig juga menjadi induk class saudara lain di proyek.
class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.events"

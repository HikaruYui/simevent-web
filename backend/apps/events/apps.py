# Fungsi file: Registrasi AppConfig Django untuk app events.

from django.apps import AppConfig


# Inheritance: EventsConfig mewarisi mekanisme konfigurasi aplikasi Django.
class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.events"

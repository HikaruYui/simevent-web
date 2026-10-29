# Fungsi file: Registrasi AppConfig Django untuk app achievements.

from django.apps import AppConfig


# Inheritance: AchievementsConfig mewarisi mekanisme konfigurasi aplikasi Django.
class AchievementsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.achievements"

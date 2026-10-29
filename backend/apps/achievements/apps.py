# Fungsi file: Registrasi AppConfig Django untuk app achievements.

from django.apps import AppConfig


# Inheritance: AchievementsConfig mewarisi mekanisme konfigurasi aplikasi Django.
# OOP — Hierarchical inheritance: AppConfig juga menjadi induk class saudara lain di proyek.
class AchievementsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.achievements"

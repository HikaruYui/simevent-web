# Fungsi file: Registrasi AppConfig Django untuk app accounts.

from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"

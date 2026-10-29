# Fungsi file: Registrasi AppConfig Django untuk app accounts.

from django.apps import AppConfig

# Inheritance: AccountsConfig mewarisi mekanisme konfigurasi aplikasi Django.
class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"

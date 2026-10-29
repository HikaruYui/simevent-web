# Fungsi file: Registrasi AppConfig Django untuk app accounts.

from django.apps import AppConfig

# Inheritance: AccountsConfig mewarisi mekanisme konfigurasi aplikasi Django.
# OOP — Hierarchical inheritance: AppConfig juga menjadi induk class saudara lain di proyek.
class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"

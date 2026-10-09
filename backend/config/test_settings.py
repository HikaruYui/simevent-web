# Fungsi file: Konfigurasi khusus pengujian PostgreSQL dengan hasher cepat; bukan untuk menjalankan server.

from .settings import *  # noqa: F403

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

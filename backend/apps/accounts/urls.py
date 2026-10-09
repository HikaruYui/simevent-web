# Fungsi file: Pemetaan URL ke view untuk akun, autentikasi, dan hak akses.

from django.urls import path
from . import views
app_name = "accounts"

urlpatterns = [
    path("csrf/", views.csrf_token, name="csrf"),
    path("register/", views.register, name="register"),
    path("login/", views.sign_in, name="login"),
    path("logout/", views.sign_out, name="logout"),
    path("profile/", views.profile, name="profile"),
]

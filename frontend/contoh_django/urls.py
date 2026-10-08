# Salin/gabungkan ke urls.py. Nama (name=...) harus persis seperti ini.
from django.urls import path
from . import views

urlpatterns = [
    path("", views.beranda, name="beranda"),
    path("masuk/", views.masuk, name="masuk"),
    path("daftar/", views.daftar, name="daftar"),
    path("lupa-password/", views.lupa_password, name="lupa_password"),
    path("jelajah/", views.jelajah, name="jelajah"),
    path("tentang/", views.tentang, name="tentang"),
    path("bantuan/", views.bantuan, name="bantuan"),
    path("event/buat/", views.buat_event, name="buat_event"),
    path("event/<int:pk>/", views.detail_event, name="detail_event"),
]

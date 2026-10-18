# Routing utama backend dan halaman frontend SIMEVENT.
from django.contrib import admin
from django.urls import include, path
from . import views

urlpatterns = [
    path(
        "",
        views.landing_page,
        name="landing",
    ),

    path(
        "tentang/",
        views.tentang,
        name="tentang",
    ),

        path(
        "bantuan/",
        views.bantuan,
        name="bantuan",
    ),

    path(
        "jelajah/",
        views.jelajah,
        name="jelajah",
    ),

    path(
        "jelajah/<slug:slug>/",
        views.detail_event,
        name="detail_event",
    ),


    path(
        "masuk/",
        views.login_page,
        name="login_page",
    ),

    path(
        "keluar/",
        views.logout_page,
        name="logout_page",
    ),

    path(
        "setelah-login/",
        views.after_login,
        name="after_login",
    ),

    path(
        "panitia/",
        views.panitia_dashboard,
        name="panitia_dashboard",
    ),

    path("ketua-panitia/", views.eo_dashboard, name="eo_dashboard"),
    path("ketua-panitia/event/", views.eo_event, name="eo_event"),
    path("ketua-panitia/peserta/", views.eo_peserta, name="eo_peserta"),
    path("ketua-panitia/pendapatan/", views.eo_pendapatan, name="eo_pendapatan"),
    path("ketua-panitia/log-aktivitas/", views.eo_log, name="eo_log"),
    path("ketua-panitia/support/", views.eo_support, name="eo_support"),

    path(
        "panitia/event/<int:pk>/",
        views.panitia_event_detail,
        name="panitia_event_detail",
    ),

    path(
        "admin/",
        admin.site.urls,
    ),

    path(
        "accounts/",
        include("apps.accounts.urls"),
    ),

    path(
        "partnerships/",
        include("apps.partnerships.urls"),
    ),

    path(
        "events/",
        include("apps.events.urls"),
    ),

    path(
        "registrations/",
        include("apps.registrations.urls"),
    ),

    path(
        "achievements/",
        include("apps.achievements.urls"),
    ),

    path(
        "peserta/akun/",
        views.peserta_akun,
        name="peserta_akun",
    ),
    path(
        "peserta/",
        views.peserta_dashboard,
        name="peserta_dashboard",
    ),
    path(
        "peserta/daftar-event/",
        views.peserta_daftar_event,
        name="peserta_daftar_event",
    ),
    path(
        "peserta/sertifikat/",
        views.peserta_sertifikat,
        name="peserta_sertifikat",
    ),
    path(
        "peserta/sertifikat/<int:pk>/",
        views.peserta_sertifikat_detail,
        name="peserta_sertifikat_detail",
    ),
    path(
        "peserta/achievement/",
        views.peserta_achievement,
        name="peserta_achievement",
    ),
]

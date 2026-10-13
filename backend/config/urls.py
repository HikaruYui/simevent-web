# Routing utama backend dan halaman frontend SIMEVENT.
from django.contrib import admin
from django.urls import include, path
from . import views

urlpatterns = [
    # Halaman publik
    path("", views.landing_page, name="landing"),
    path("tentang/", views.tentang, name="tentang"),
    path("jelajah/", views.jelajah, name="jelajah"),
    path(
        "jelajah/<slug:slug>/",
        views.detail_event,
        name="detail_event",
    ),

    # Halaman login dan pengalihan setelah login
    path("masuk/", views.login_page, name="login_page"),
    path("keluar/", views.logout_page, name="logout_page"),
    path(
        "setelah-login/",
        views.after_login,
        name="after_login",
    ),

    # Halaman panitia
    path(
        "panitia/",
        views.panitia_dashboard,
        name="panitia_dashboard",
    ),
    path(
        "panitia/events/<int:pk>/",
        views.panitia_event_detail,
        name="panitia_event_detail",
    ),

    # Django Admin dan endpoint aplikasi
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("partnerships/", include("apps.partnerships.urls")),
    path("events/", include("apps.events.urls")),
    path("registrations/", include("apps.registrations.urls")),
    path("achievements/", include("apps.achievements.urls")),
]

# Fungsi file: Routing utama yang menghubungkan Django Admin dan URL kelima app backend.

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("partnerships/", include("apps.partnerships.urls")),
    path("events/", include("apps.events.urls")),
    path("registrations/", include("apps.registrations.urls")),
    path("achievements/", include("apps.achievements.urls")),
]

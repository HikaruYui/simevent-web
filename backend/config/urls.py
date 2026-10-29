# Routing utama backend dan halaman frontend SIMEVENT.
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from . import views

urlpatterns = [
    path("masuk/reset/", auth_views.PasswordResetView.as_view(
        template_name="password_reset.html", email_template_name="emails/password_reset.txt",
        subject_template_name="emails/password_reset_subject.txt",
    ), name="password_reset"),
    path("masuk/reset/terkirim/", auth_views.PasswordResetDoneView.as_view(
        template_name="password_reset.html", extra_context={"reset_sent": True},
    ), name="password_reset_done"),
    path("masuk/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="password_reset.html", extra_context={"reset_confirm": True},
    ), name="password_reset_confirm"),
    path("masuk/reset/selesai/", auth_views.PasswordResetCompleteView.as_view(
        template_name="password_reset.html", extra_context={"reset_complete": True},
    ), name="password_reset_complete"),
    # Jalur terpisah agar tidak bentrok dengan API /accounts/.
    path("auth/", include("allauth.urls")),
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
    path(
        "panitia_biasa/",
        views.panitia_biasa_dashboard,
        name="panitia_biasa",
    ),
    path(
        "panitia_biasa/akun/",
        views.panitia_akun,
        name="panitia_akun",
    ),
    path(
        "panitia_biasa/profil/",
        views.panitia_simpan_profil,
        name="panitia_simpan_profil",
    ),

    path("ketua-panitia/", views.eo_dashboard, name="eo_dashboard"),
    path("ketua-panitia/event/", views.eo_event, name="eo_event"),
    path("ketua-panitia/peserta/", views.eo_peserta, name="eo_peserta"),
    path("ketua-panitia/pendapatan/", views.eo_pendapatan, name="eo_pendapatan"),
    path("ketua-panitia/log-aktivitas/", views.eo_log, name="eo_log"),
    path("ketua-panitia/support/", views.eo_support, name="eo_support"),
    path("ketua-panitia/pengaturan/", views.eo_pengaturan, name="eo_pengaturan"),
    path("ketua-panitia/api/support/<str:code>/resolve/", views.eo_support_resolve, name="eo_support_resolve"),
    path("ketua-panitia/api/settings/profile/", views.eo_settings_profile, name="eo_settings_profile"),
    path("ketua-panitia/api/settings/password/", views.eo_settings_password, name="eo_settings_password"),
    path("ketua-panitia/api/settings/notification/", views.eo_settings_notification, name="eo_settings_notification"),
    path("ketua-panitia/api/settings/team/", views.eo_settings_team, name="eo_settings_team"),
    path("ketua-panitia/api/settings/invitations/", views.eo_settings_invite, name="eo_settings_invite"),
    path("ketua-panitia/api/settings/invitations/<int:pk>/", views.eo_settings_invitation_action, name="eo_settings_invitation_action"),
    path("undangan/<uuid:token>/", views.eo_invitation_accept, name="eo_invitation_accept"),
    path("admin-panel/", views.admin_dashboard, name="admin_dashboard"),
    path("admin-panel/users/", views.admin_users, name="admin_users"),
    path("admin-panel/events/", views.admin_events, name="admin_events"),
    path("admin-panel/finance/", views.admin_finance, name="admin_finance"),
    path("admin-panel/audit/", views.admin_audit, name="admin_audit"),
    path("admin-panel/settings/", views.admin_settings, name="admin_settings"),
    path("admin-panel/api/users/", views.admin_user_mutation, name="admin_user_create"),
    path("admin-panel/api/users/<int:pk>/", views.admin_user_mutation, name="admin_user_mutation"),
    path("admin-panel/api/proposals/<int:pk>/review/", views.admin_proposal_review, name="admin_proposal_review"),
    path("admin-panel/api/support/<str:code>/", views.admin_support_mutation, name="admin_support_mutation"),
    path("admin-panel/api/payouts/", views.admin_payout, name="admin_payout"),
    path("admin-panel/api/settings/", views.admin_settings_mutation, name="admin_settings_mutation"),
    path("admin-panel/api/profile/", views.admin_profile_mutation, name="admin_profile_mutation"),
    path("admin-panel/support/", views.admin_support, name="admin_support"),

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

    path("ketua-panitia/event/", views.eo_event, name="eo_event"),
    
    path(
        "ketua-panitia/api/events/<int:event_id>/committee/",
        views.eo_event_committee,
        name="eo_event_committee",
    ),

    path(
        "achievements/",
        include("apps.achievements.urls"),
    ),

    path(
        "akun/foto-profil/",
        views.foto_profil,
        name="foto_profil",
    ),
    path(
        "peserta/akun/",
        views.peserta_akun,
        name="peserta_akun",
    ),
    path(
        "peserta/akun/hapus-foto/",
        views.peserta_hapus_foto,
        name="peserta_hapus_foto",
    ),
    path(
        "panitia_biasa/dokumentasi/simpan/",
        views.panitia_simpan_dokumentasi,
        name="panitia_simpan_dokumentasi",
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
        "peserta/event-saya/",
        views.peserta_event_saya,
        name="peserta_event_saya",
    ),
    path(
        "peserta/dokumentasi/<int:event_id>/",
        views.peserta_dokumentasi,
        name="peserta_dokumentasi",
    ),
    path(
        "peserta/sertifikat/",
        views.peserta_sertifikat,
        name="peserta_sertifikat",
    ),
    path(
        "panitia_biasa/sertifikat/unggah/",
        views.panitia_upload_sertifikat,
        name="panitia_upload_sertifikat",
    ),
    path(
        "panitia_biasa/sertifikat/hapus/",
        views.panitia_hapus_sertifikat,
        name="panitia_hapus_sertifikat",
    ),
    path(
        "peserta/sertifikat/<int:pk>/unggahan/",
        views.peserta_sertifikat_unggahan,
        name="peserta_sertifikat_unggahan",
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

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

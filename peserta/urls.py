from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='peserta_dashboard'),
    path('events/', views.my_events, name='peserta_events'),
    path('certificates/', views.certificates, name='peserta_certificates'),
    path('certificates/<int:cert_id>/claim/', views.claim_certificate, name='peserta_claim_certificate'),
    path('payments/', views.payments, name='peserta_payments'),
    path('profile/', views.profile, name='peserta_profile'),
]

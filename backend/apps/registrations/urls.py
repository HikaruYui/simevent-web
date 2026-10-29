# OOP — Factory / dynamic dispatch: as_view() mengadaptasi class menjadi callable URL; setiap request memakai instance yang memilih handler get/post melalui dispatch.
# Fungsi file: Pemetaan URL ke view untuk registrasi, tiket, attendance, feedback, dan statistik.

from django.urls import path

from . import views
from .attendance_views import AttendanceDetailView, AttendanceVoidView, TicketScanView
from .feedback_views import FeedbackDetailView, FeedbackResultsView
from .statistics_views import EventStatisticsView, StatisticsOverviewView

app_name = "registrations"
urlpatterns = [
    path("statistics/", StatisticsOverviewView.as_view(), name="statistics"),
    path("events/<int:event_id>/statistics/", EventStatisticsView.as_view(), name="event-statistics"),
    path("<int:pk>/feedback/", FeedbackDetailView.as_view(), name="feedback"),
    path("events/<int:event_id>/feedback/", FeedbackResultsView.as_view(), name="feedback-results"),
    path("events/<int:event_id>/scan/", TicketScanView.as_view(), name="scan"),
    path("events/<int:event_id>/register-paid/", views.PaidRegistrationCreateView.as_view(), name="register-paid"),
    path("<int:pk>/payment/", views.PaymentProofView.as_view(), name="payment"),
    path("payments/<int:pk>/proof/", views.PaymentProofDownloadView.as_view(), name="payment-proof-download"),
    path("payments/<int:pk>/review/", views.PaymentReviewView.as_view(), name="payment-review"),
    path("<int:pk>/certificate.pdf", views.CertificatePDFView.as_view(), name="certificate-pdf"),
    path("<int:pk>/attendance/", AttendanceDetailView.as_view(), name="attendance"),
    path("<int:pk>/attendance/void/", AttendanceVoidView.as_view(), name="attendance-void"),
    path("", views.RegistrationListView.as_view(), name="list"),
    path("events/<int:event_id>/register/", views.RegistrationCreateView.as_view(), name="create"),
    path("events/<int:event_id>/participants/", views.ParticipantListView.as_view(), name="participants"),
    path("<int:pk>/cancel/", views.RegistrationCancelView.as_view(), name="cancel"),
    path("<int:pk>/ticket/", views.TicketDetailView.as_view(), name="ticket"),
    path("<int:pk>/ticket/qr/", views.TicketQRView.as_view(), name="ticket-qr"),
    path("<int:pk>/meeting/", views.MeetingAccessView.as_view(), name="meeting"),
]

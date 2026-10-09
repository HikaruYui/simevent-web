# Fungsi file: Pemetaan URL ke view untuk proposal kerja sama dan approval Organizer.

from django.urls import path

from .views import ProposalDeleteView, ProposalDetailView, ProposalListView, ProposalSubmitView

app_name = "partnerships"
urlpatterns = [
    path("proposals/", ProposalListView.as_view(), name="list"),
    path("proposals/<int:pk>/", ProposalDetailView.as_view(), name="detail"),
    path("proposals/<int:pk>/submit/", ProposalSubmitView.as_view(), name="submit"),
    path("proposals/<int:pk>/delete/", ProposalDeleteView.as_view(), name="delete"),
]

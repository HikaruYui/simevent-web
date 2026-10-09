# Fungsi file: Pemetaan URL ke view untuk event, ownership, dan alur approval/publikasi.

from django.urls import path

from . import views

app_name = "events"
urlpatterns = [
    path("", views.EventListView.as_view(), name="list"),
    path("manage/", views.ManagedEventListView.as_view(), name="manage-list"),
    path("manage/<int:pk>/", views.ManagedEventDetailView.as_view(), name="manage-detail"),
    path("manage/<int:pk>/delete/", views.EventDeleteView.as_view(), name="delete"),
    path("manage/<int:pk>/<str:action>/", views.EventTransitionView.as_view(), name="transition"),
    path("<slug:slug>/", views.EventDetailView.as_view(), name="detail"),
]

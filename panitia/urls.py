from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='panitia_dashboard'),
    path('events/', views.manage_events, name='panitia_manage_events'),
    path('events/create/', views.create_event, name='panitia_create_event'),
    path('events/<int:event_id>/participants/', views.event_participants, name='panitia_participants'),
]

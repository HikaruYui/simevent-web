# Fungsi file: Endpoint statistik per event dan dashboard dengan ownership serta pagination.

from django.core.exceptions import PermissionDenied
from django.db.models import Count, F, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.generic import ListView

from apps.events.models import Event, EventStatus
from apps.events.views import EventManagementMixin

from .models import Registration
from .statistics import participation_metrics, statistics_data


class StatisticsAccessMixin(EventManagementMixin):
    def get_events(self):
        if not self.request.user.has_perm("registrations.view_feedback"):
            raise PermissionDenied
        return Event.objects.managed_by(self.request.user)


class EventStatisticsView(StatisticsAccessMixin, View):
    http_method_names = ["get", "head", "options"]

    def get(self, request, event_id):
        event = get_object_or_404(self.get_events(), pk=event_id)
        metrics = Registration.objects.filter(event=event).aggregate(**participation_metrics())
        return JsonResponse({
            "event_id": event.pk,
            "event_title": event.title,
            "event_status": event.status,
            "capacity": event.capacity,
            **statistics_data(metrics),
        })


class StatisticsOverviewView(StatisticsAccessMixin, ListView):
    paginate_by = 20
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        self.events = self.get_events()
        return self.events.values(
            "id", "title", "status", "capacity", "start_datetime",
            event_type_code=F("event_type__code"),
        ).annotate(**participation_metrics("registrations__")).order_by("start_datetime", "pk")

    def render_to_response(self, context, **response_kwargs):
        events = self.events.aggregate(
            total_events=Count("pk"),
            **{status: Count("pk", filter=Q(status=status)) for status in EventStatus.values},
        )
        summary = Registration.objects.filter(event__in=self.events).aggregate(
            **participation_metrics(),
        )
        return JsonResponse({
            "summary": {
                "total_events": events.pop("total_events"),
                "events_by_status": events,
                **statistics_data(summary),
            },
            "results": [statistics_data(row) for row in context["object_list"]],
            "page": context["page_obj"].number,
            "pages": context["paginator"].num_pages,
        })

# Fungsi file: Endpoint feedback peserta dan hasil/ringkasan feedback dalam scope Organizer/Admin.

from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.generic import ListView

from apps.accounts.permissions import require_organizer
from apps.events.models import Event

from .feedback import FeedbackService
from .models import Feedback, RATING_FIELDS
from .views import ParticipantAccessMixin


def feedback_data(feedback):
    return {
        "id": feedback.pk,
        **{field: getattr(feedback, field) for field in RATING_FIELDS},
        "comment": feedback.comment,
        "suggestion": feedback.suggestion,
        "created_at": feedback.created_at,
    }


class FeedbackDetailView(ParticipantAccessMixin, View):
    http_method_names = ["get", "post", "head", "options"]

    def get(self, request, pk):
        feedback = get_object_or_404(
            Feedback.objects.filter(registration__participant=request.user),
            registration_id=pk,
        )
        return JsonResponse(feedback_data(feedback))

    def post(self, request, pk):
        feedback = FeedbackService(request.user).submit(pk, data=request.POST)
        return JsonResponse(feedback_data(feedback), status=201)


class FeedbackResultsView(ParticipantAccessMixin, ListView):
    paginate_by = 20
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        actor = self.request.user
        require_organizer(actor)
        if not actor.has_perm("registrations.view_feedback"):
            raise PermissionDenied
        event = get_object_or_404(
            Event.objects.managed_by(actor), pk=self.kwargs["event_id"],
        )
        return Feedback.objects.eligible().filter(registration__event=event)

    def render_to_response(self, context, **response_kwargs):
        summary = self.object_list.aggregate(
            feedback_count=Count("pk"),
            **{f"average_{field}": Avg(field) for field in RATING_FIELDS},
        )
        return JsonResponse({
            "summary": summary,
            "results": [feedback_data(item) for item in context["object_list"]],
            "page": context["page_obj"].number,
            "pages": context["paginator"].num_pages,
        })

# Fungsi file: Penanganan request HTTP, scope akses, dan respons untuk registrasi, tiket, attendance, feedback, dan statistik.

from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import ListView

from apps.accounts.permissions import require_organizer
from apps.events.models import Event

from .forms import ConfirmationForm
from .models import Registration, Ticket
from .services import RegistrationService
from .tickets import render_ticket_qr


def registration_data(registration):
    return {
        "id": registration.pk,
        "event_id": registration.event_id,
        "event_title": registration.event.title,
        "event_status": registration.event.status,
        "status": registration.status,
        "registered_at": registration.registered_at,
        "cancelled_at": registration.cancelled_at,
    }


def attendance_data(attendance):
    if attendance is None:
        return {"status": "NOT_CHECKED_IN", "checked_in_at": None}
    return {"status": attendance.status, "checked_in_at": attendance.checked_in_at}


@method_decorator(never_cache, name="dispatch")
class ParticipantAccessMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_active:
            return JsonResponse({"error": "Authentication required."}, status=401)
        try:
            return super().dispatch(request, *args, **kwargs)
        except ValidationError as exc:
            errors = exc.message_dict if hasattr(exc, "message_dict") else {"__all__": exc.messages}
            return JsonResponse({"errors": errors}, status=400)


class RegistrationListView(ParticipantAccessMixin, ListView):
    paginate_by = 20
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        return Registration.objects.owned_by(self.request.user).select_related("event")

    def render_to_response(self, context, **response_kwargs):
        return JsonResponse({
            "results": [registration_data(item) for item in context["object_list"]],
            "page": context["page_obj"].number,
            "pages": context["paginator"].num_pages,
        })


class RegistrationCreateView(ParticipantAccessMixin, View):
    http_method_names = ["post", "options"]

    def post(self, request, event_id):
        form = ConfirmationForm(request.POST)
        if not form.is_valid():
            raise ValidationError(form.errors.as_data())
        registration = RegistrationService(request.user).register(event_id)
        return JsonResponse(registration_data(registration), status=201)


class RegistrationCancelView(ParticipantAccessMixin, View):
    http_method_names = ["post", "options"]

    def post(self, request, pk):
        get_object_or_404(Registration.objects.owned_by(request.user), pk=pk)
        form = ConfirmationForm(request.POST)
        if not form.is_valid():
            raise ValidationError(form.errors.as_data())
        registration = RegistrationService(request.user).cancel(pk)
        return JsonResponse(registration_data(registration))


class TicketAccessMixin(ParticipantAccessMixin):
    def get_ticket(self, request, pk):
        return get_object_or_404(
            Ticket.objects.select_related(
                "registration__event", "registration__participant",
            ).filter(registration__participant=request.user),
            registration_id=pk,
        )


class TicketDetailView(TicketAccessMixin, View):
    http_method_names = ["get", "head", "options"]

    def get(self, request, pk):
        ticket = self.get_ticket(request, pk)
        is_valid = ticket.is_valid
        return JsonResponse({
            "identifier": ticket.identifier,
            "registration": registration_data(ticket.registration),
            "is_valid": is_valid,
            "token": ticket.token if is_valid else None,
        })


class TicketQRView(TicketAccessMixin, View):
    http_method_names = ["get", "head", "options"]

    def get(self, request, pk):
        ticket = self.get_ticket(request, pk)
        if not ticket.is_valid:
            raise ValidationError("This ticket is not valid.")
        response = HttpResponse(render_ticket_qr(ticket.token), content_type="image/png")
        response["Content-Disposition"] = 'inline; filename="ticket.png"'
        return response


class MeetingAccessView(TicketAccessMixin, View):
    http_method_names = ["get", "head", "options"]

    def get(self, request, pk):
        ticket = self.get_ticket(request, pk)
        if not ticket.is_valid:
            raise ValidationError("Active registration for a published event is required.")
        access = getattr(ticket.registration.event, "private_access", None)
        return JsonResponse({
            "meeting_url": access.meeting_url if access else "",
            "instructions": access.instructions if access else "",
        })


class ParticipantListView(RegistrationListView):
    def get_queryset(self):
        require_organizer(self.request.user)
        event = get_object_or_404(
            Event.objects.managed_by(self.request.user), pk=self.kwargs["event_id"],
        )
        return Registration.objects.filter(event=event).select_related(
            "event", "participant", "attendance",
        )

    def render_to_response(self, context, **response_kwargs):
        response = {
            "results": [{
                **registration_data(item),
                "attendance": attendance_data(getattr(item, "attendance", None)),
                "participant": {
                    "id": item.participant_id,
                    "name": item.participant.get_full_name(),
                    "email": item.participant.email,
                },
            } for item in context["object_list"]],
            "page": context["page_obj"].number,
            "pages": context["paginator"].num_pages,
        }
        return JsonResponse(response)

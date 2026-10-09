# Fungsi file: Penanganan request HTTP, scope akses, dan respons untuk event, ownership, dan alur approval/publikasi.

from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import DetailView, ListView

from apps.accounts.permissions import require_organizer

from .forms import DeleteDraftForm, TransitionForm
from .models import Event
from .workflow import EventWorkflow


def event_data(event):
    """Explicit public fields; never serialize a model or its relations wholesale."""
    return {
        "id": event.pk,
        "slug": event.slug,
        "title": event.title,
        "description": event.description,
        "event_type": {"code": event.event_type.code, "name": event.event_type.name},
        "delivery_mode": event.delivery_mode,
        "start_datetime": event.start_datetime,
        "end_datetime": event.end_datetime,
        "venue": event.venue,
        "capacity": event.capacity,
        "price": event.price,
        "registration_open": event.registration_open,
        "registration_close": event.registration_close,
        "banner_url": event.banner.url if event.banner else None,
        "status": event.status,
        "is_ongoing": event.is_ongoing,
    }


@method_decorator(never_cache, name="dispatch")
class EventListView(ListView):
    model = Event
    paginate_by = 20
    http_method_names = ["get", "head", "options"]

    # Polymorphism: hook get_queryset pada view publik mengembalikan event yang boleh dilihat umum.
    def get_queryset(self):
        return Event.objects.public().select_related("event_type")

    def render_to_response(self, context, **response_kwargs):
        return JsonResponse({
            "results": [event_data(event) for event in context["object_list"]],
            "page": context["page_obj"].number,
            "pages": context["paginator"].num_pages,
        })


@method_decorator(never_cache, name="dispatch")
class EventDetailView(DetailView):
    model = Event
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        return Event.objects.public().select_related("event_type")

    def render_to_response(self, context, **response_kwargs):
        return JsonResponse(event_data(context["object"]))


@method_decorator(never_cache, name="dispatch")
class EventManagementMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required."}, status=401)
        require_organizer(request.user)
        try:
            return super().dispatch(request, *args, **kwargs)
        except ValidationError as exc:
            errors = exc.message_dict if hasattr(exc, "message_dict") else {"__all__": exc.messages}
            return JsonResponse({"errors": errors}, status=400)

    # Polymorphism: hook get_queryset pada view pengelolaan memakai scope Organizer/Admin.
    def get_queryset(self):
        return Event.objects.managed_by(self.request.user).select_related("event_type")


class ManagedEventListView(EventManagementMixin, EventListView):
    http_method_names = ["get", "post", "head", "options"]

    def post(self, request):
        event = EventWorkflow(request.user).create(data=request.POST, files=request.FILES)
        return JsonResponse(event_data(event), status=201)


class ManagedEventDetailView(EventManagementMixin, EventDetailView):
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return super().get_queryset().select_related("private_access")

    def render_to_response(self, context, **response_kwargs):
        event = context["object"]
        data = event_data(event)
        access = getattr(event, "private_access", None)
        data["meeting_url"] = access.meeting_url if access else ""
        data["access_instructions"] = access.instructions if access else ""
        data["transitions"] = list(event.transitions.values(
            "from_status", "to_status", "reason", "created_at"
        ))
        return JsonResponse(data)

    def post(self, request, pk):
        event = EventWorkflow(request.user).update(pk, data=request.POST, files=request.FILES)
        return JsonResponse(event_data(event))


class EventTransitionView(EventManagementMixin, View):
    http_method_names = ["post", "options"]

    def post(self, request, pk, action):
        form = TransitionForm(request.POST)
        if not form.is_valid():
            raise ValidationError(form.errors.as_data())
        event = EventWorkflow(request.user).transition(pk, action=action, **form.cleaned_data)
        return JsonResponse(event_data(event))


class EventDeleteView(EventManagementMixin, DetailView):
    model = Event
    http_method_names = ["post", "options"]

    def post(self, request, pk):
        self.get_object()
        form = DeleteDraftForm(request.POST)
        if not form.is_valid():
            raise ValidationError(form.errors.as_data())
        EventWorkflow(request.user).delete_draft(pk)
        return JsonResponse({"deleted": True})

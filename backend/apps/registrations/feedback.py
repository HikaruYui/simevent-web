# Fungsi file: Pengiriman feedback satu kali dengan validasi registrasi, kehadiran, dan event selesai.

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404

from apps.accounts.services import lock_accounts
from apps.events.models import Event, EventStatus

from .forms import FeedbackForm
from .models import Attendance, Feedback, Registration, RegistrationStatus


class FeedbackService:
    """Submit once, under the same event lock used by attendance moderation."""

    def __init__(self, actor):
        if not actor.is_authenticated:
            raise PermissionDenied
        self._actor_id = actor.pk

    @transaction.atomic
    def submit(self, registration_id, *, data):
        actor = lock_accounts(self._actor_id).get(self._actor_id)
        if actor is None or not actor.is_active:
            raise PermissionDenied
        registration = get_object_or_404(
            Registration.objects.owned_by(actor), pk=registration_id,
        )
        event = Event.objects.select_for_update().get(pk=registration.event_id)
        registration.refresh_from_db()
        if (
            registration.status != RegistrationStatus.REGISTERED
            or event.status != EventStatus.COMPLETED
            or not Attendance.objects.filter(
                registration=registration, status=Attendance.Status.PRESENT,
            ).exists()
        ):
            raise ValidationError("Feedback requires valid attendance at a completed event.")
        if Feedback.objects.filter(registration=registration).exists():
            raise ValidationError("Feedback has already been submitted and cannot be changed.")
        form = FeedbackForm(data, instance=Feedback(registration=registration))
        if not form.is_valid():
            raise ValidationError(form.errors.as_data())
        return form.save()

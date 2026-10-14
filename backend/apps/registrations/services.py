# Fungsi file: Pendaftaran, pembatalan, pengecekan kuota, dan penerbitan tiket dalam transaksi.

from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.accounts.services import lock_accounts
from apps.events.models import Event, EventStatus

from .models import Registration, RegistrationStatus, Ticket


# Encapsulation: menyatukan identitas actor, aturan registrasi, kuota, dan tiket dalam satu service.
class RegistrationService:
    """Serialize seat changes with event transitions and issue tickets atomically."""

    def __init__(self, actor):
        if not actor.is_authenticated:
            raise PermissionDenied
        self._actor_id = actor.pk

    def _lock_actor(self):
        actor = lock_accounts(self._actor_id)[self._actor_id]
        if not actor.is_active:
            raise PermissionDenied
        return actor

    # OOP — Abstraction: satu operasi pendaftaran menangani validasi, penguncian kuota, dan penerbitan tiket.
    @transaction.atomic
    def register(self, event_id):
        actor = self._lock_actor()
        event = get_object_or_404(Event.objects.public().select_for_update(), pk=event_id)
        now = timezone.now()
        if event.status != EventStatus.PUBLISHED:
            raise ValidationError("Registration requires a published event.")
        if not event.registration_open <= now < event.registration_close:
            raise ValidationError("Registration is not open.")
        if now >= event.start_datetime or event.price != 0:
            raise ValidationError("Only upcoming free events accept registration.")

        registration = Registration.objects.filter(participant=actor, event=event).first()
        if registration and registration.status == RegistrationStatus.REGISTERED:
            raise ValidationError("You are already registered.")
        if event.registrations.active().count() >= event.capacity:
            raise ValidationError("This event is full.")

        if registration is None:
            registration = Registration.objects.create(
                participant=actor, event=event, registered_at=now,
            )
            Ticket.objects.create(registration=registration)
        else:
            registration.status = RegistrationStatus.REGISTERED
            registration.registered_at = now
            registration.cancelled_at = None
            registration.save(update_fields=[
                "status", "registered_at", "cancelled_at", "updated_at",
            ])
            Ticket.objects.update_or_create(
                registration=registration,
                defaults={"token": uuid4(), "is_active": True},
            )
        return registration

    @transaction.atomic
    def cancel(self, registration_id):
        actor = self._lock_actor()
        registration = get_object_or_404(
            Registration.objects.owned_by(actor), pk=registration_id,
        )
        event = Event.objects.select_for_update().get(pk=registration.event_id)
        registration.refresh_from_db()
        if registration.status == RegistrationStatus.CANCELLED:
            return registration
        now = timezone.now()
        if event.status != EventStatus.CANCELLED and now >= event.start_datetime:
            raise ValidationError("Registration can only be cancelled before event start.")
        registration.status = RegistrationStatus.CANCELLED
        registration.cancelled_at = now
        registration.save(update_fields=["status", "cancelled_at", "updated_at"])
        Ticket.objects.filter(registration=registration).update(is_active=False)
        return registration

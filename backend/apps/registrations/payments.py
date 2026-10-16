from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.accounts.permissions import require_organizer
from apps.accounts.services import lock_accounts
from apps.events.models import Event

from .models import Payment, RegistrationStatus, Ticket


class PaymentService:
    def __init__(self, actor):
        if not actor.is_authenticated:
            raise PermissionDenied
        self._actor_id = actor.pk

    @transaction.atomic
    def review(self, payment_id, *, approve, note=""):
        payment = get_object_or_404(
            Payment.objects.select_related("registration"),
            pk=payment_id,
        )
        accounts = lock_accounts(self._actor_id, payment.registration.participant_id)
        actor = accounts.get(self._actor_id)
        if actor is None or not actor.is_active:
            raise PermissionDenied
        require_organizer(actor)
        event = get_object_or_404(
            Event.objects.managed_by(actor).select_for_update(),
            pk=payment.registration.event_id,
        )
        payment = get_object_or_404(
            Payment.objects.select_for_update().select_related("registration"),
            pk=payment_id,
        )
        if payment.registration.status != RegistrationStatus.REGISTERED:
            raise ValidationError("Pendaftaran ini sudah dibatalkan.")
        if payment.status != Payment.Status.UNDER_REVIEW:
            raise ValidationError("Bukti pembayaran belum dikirim atau sudah ditinjau.")
        if not approve and not note.strip():
            raise ValidationError("Alasan penolakan wajib diisi.")
        if len(note) > 2000:
            raise ValidationError("Catatan maksimal 2000 karakter.")

        now = timezone.now()
        payment.reviewed_by = actor
        payment.reviewed_at = now
        payment.review_note = note.strip()
        payment.status = Payment.Status.APPROVED if approve else Payment.Status.REJECTED
        payment.save(update_fields=[
            "status", "reviewed_by", "reviewed_at", "review_note",
        ])
        if approve:
            Ticket.objects.get_or_create(registration=payment.registration)
        return payment

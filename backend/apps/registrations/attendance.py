# Fungsi file: Validasi scan tiket, pencatatan attendance, dan pembatalan attendance oleh Admin.

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables
from apps.accounts.models import User
from apps.accounts.permissions import require_organizer
from apps.accounts.services import lock_accounts, require_platform_permission
from apps.events.models import Event, EventStatus
from .forms import TicketScanForm
from .models import Attendance, RegistrationStatus, Ticket
from django.db.models import Q


# Encapsulation: identitas pelaku, aturan scan, dan pembatalan kehadiran disatukan dalam objek service.
class AttendanceService:
    """Validate event scope and serialize attendance with registration changes."""

    # Encapsulation: _actor_id menyimpan identitas pelaku per objek; awalan _ adalah konvensi internal, bukan akses privat yang dipaksakan Python.
    def __init__(self, actor):
        if not actor.is_authenticated:
            raise PermissionDenied
        self._actor_id = actor.pk
    

    # Encapsulation: helper berawalan _ menandai detail internal class menurut konvensi Python.
    def _require_scanner_access(self, actor):
        if not actor.is_active:
            raise PermissionDenied

        # Panitia Biasa menggunakan penugasan event sebagai izin.
        if actor.role == "COMMITTEE":
            return

        # Hak akses Organizer/Admin tetap seperti semula.
        require_organizer(actor)
        if not actor.has_perm("registrations.scan_ticket"):
            raise PermissionDenied

    
  
    
    def _scannable_events(self, actor):
        managed_events = Event.objects.managed_by(actor)

        if actor.role == "COMMITTEE":
            assigned_event_ids = Event.objects.filter(
                committee_assignments__member=actor,
                committee_assignments__is_active=True,
            ).values("pk")

            return Event.objects.filter(
                Q(pk__in=managed_events.values("pk"))
                | Q(pk__in=assigned_event_ids)
            )

        return managed_events





    def _scanner(self):
        actor = get_object_or_404(User, pk=self._actor_id)
        self._require_scanner_access(actor)
        return actor


    # Abstraction: mencatat kehadiran melalui satu method yang memeriksa akses, tiket, dan waktu event.
    @sensitive_variables("token", "ticket")
    @transaction.atomic
    def scan(self, event_id, *, token):
        actor = self._scanner()
        get_object_or_404(self._scannable_events(actor), pk=event_id)
        form = TicketScanForm({"token": token})
        if not form.is_valid():
            raise ValidationError("Invalid ticket.")
        token = form.cleaned_data["token"]
        # QR membawa token rahasia; input manual dari daftar memakai identifier.
        ticket = Ticket.objects.filter(
            Q(token=token) | Q(identifier=token),
            registration__event_id=event_id,
        ).select_related("registration__payment").first()
        if ticket is None:
            raise ValidationError("Invalid ticket.")

        # Account locks precede event locks in every workflow to avoid deadlocks.
        users = lock_accounts(actor.pk, ticket.registration.participant_id)
        actor = users[actor.pk]
        self._require_scanner_access(actor)
        
        event = get_object_or_404(
            self._scannable_events(actor).select_for_update(),
            pk=event_id,
        )

        ticket = Ticket.objects.filter(
            Q(token=token) | Q(identifier=token),
            registration__event=event,
        ).select_related("registration__payment").first()
        if (
            ticket is None or not ticket.is_active
            or ticket.registration.status != RegistrationStatus.REGISTERED
            or (
                hasattr(ticket.registration, "payment")
                and ticket.registration.payment.status != ticket.registration.payment.Status.APPROVED
            )
            or not users[ticket.registration.participant_id].is_active
        ):
            raise ValidationError("Invalid ticket.")
        now = timezone.now()
        if (
            event.status != EventStatus.PUBLISHED
            or not event.start_datetime <= now < event.end_datetime
        ):
            raise ValidationError("Check-in is only available during the published event.")
        attendance = Attendance.objects.filter(registration=ticket.registration).first()
        if attendance:
            if attendance.status == Attendance.Status.VOIDED:
                raise ValidationError("This attendance was voided; contact an administrator.")
            return attendance, False
        attendance = Attendance.objects.create(
            registration=ticket.registration, checked_in_at=now, verified_by=actor,
        )
        return attendance, True

    # Abstraction: membatalkan kehadiran melalui satu method yang memeriksa izin dan mencatat alasan.
    @transaction.atomic
    def void(self, attendance_id, *, reason):
        actor = lock_accounts(self._actor_id)[self._actor_id]
        require_platform_permission(actor, "registrations.void_attendance")
        reason = reason.strip()
        if not reason or len(reason) > 2000:
            raise ValidationError("A reason of 1–2000 characters is required.")
        attendance = get_object_or_404(
            Attendance.objects.select_related("registration"), pk=attendance_id,
        )
        Event.objects.select_for_update().get(pk=attendance.registration.event_id)
        attendance.refresh_from_db()
        if attendance.status == Attendance.Status.VOIDED:
            raise ValidationError("This attendance is already voided.")
        attendance.status = Attendance.Status.VOIDED
        attendance.voided_at = timezone.now()
        attendance.voided_by = actor
        attendance.void_reason = reason
        attendance.save(update_fields=["status", "voided_at", "voided_by", "void_reason"])
        return attendance

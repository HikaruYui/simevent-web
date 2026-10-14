# Fungsi file: Model, relasi, queryset, dan constraint database untuk registrasi, tiket, attendance, feedback, dan statistik.

from uuid import uuid4

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.events.models import EventStatus


class RegistrationStatus(models.TextChoices):
    REGISTERED = "REGISTERED", "Registered"
    CANCELLED = "CANCELLED", "Cancelled"


class RegistrationQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status=RegistrationStatus.REGISTERED)

    def owned_by(self, user):
        if not user.is_authenticated or not user.is_active:
            return self.none()
        return self.filter(participant=user)


class Registration(models.Model):
    participant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="registrations",
    )
    event = models.ForeignKey(
        "events.Event", on_delete=models.PROTECT, related_name="registrations",
    )
    status = models.CharField(
        max_length=10, choices=RegistrationStatus.choices,
        default=RegistrationStatus.REGISTERED,
    )
    registered_at = models.DateTimeField(default=timezone.now)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = RegistrationQuerySet.as_manager()

    class Meta:
        ordering = ("-registered_at", "-pk")
        constraints = [
            models.UniqueConstraint(
                fields=["participant", "event"], name="registration_unique_participant_event",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="REGISTERED", cancelled_at__isnull=True)
                    | models.Q(status="CANCELLED", cancelled_at__isnull=False)
                ),
                name="registration_status_timestamp_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(cancelled_at__isnull=True)
                | models.Q(cancelled_at__gte=models.F("registered_at")),
                name="registration_cancel_after_registration",
            ),
        ]
        indexes = [
            models.Index(fields=["event", "status"], name="registration_event_status_idx"),
        ]

    def __str__(self):
        return f"Registration #{self.pk} for event #{self.event_id}"


class Ticket(models.Model):
    registration = models.OneToOneField(
        Registration, on_delete=models.PROTECT, related_name="ticket",
    )
    identifier = models.UUIDField(default=uuid4, unique=True, editable=False)
    token = models.UUIDField(default=uuid4, unique=True, editable=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Encapsulation: aturan validitas tiket, registrasi, peserta, event, dan waktu dirangkum dalam property.
    @property
    def is_valid(self):
        registration = self.registration
        return (
            self.is_active
            and registration.status == RegistrationStatus.REGISTERED
            and registration.participant.is_active
            and registration.event.status == EventStatus.PUBLISHED
            and timezone.now() < registration.event.end_datetime
        )

    def __str__(self):
        return str(self.identifier)


class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = "PRESENT", "Present"
        VOIDED = "VOIDED", "Voided"

    registration = models.OneToOneField(
        Registration, on_delete=models.PROTECT, related_name="attendance",
    )
    checked_in_at = models.DateTimeField(default=timezone.now)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="verified_attendances",
    )
    status = models.CharField(max_length=7, choices=Status.choices, default=Status.PRESENT)
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="voided_attendances",
    )
    void_reason = models.TextField(max_length=2000, blank=True)

    class Meta:
        ordering = ("-checked_in_at", "-pk")
        permissions = [
            ("scan_ticket", "Can scan tickets for managed events"),
            ("void_attendance", "Can void an attendance record"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(status="PRESENT", voided_at__isnull=True,
                             voided_by__isnull=True, void_reason="")
                    | (
                        models.Q(status="VOIDED", voided_at__isnull=False,
                                 voided_by__isnull=False)
                        & ~models.Q(void_reason="")
                    )
                ),
                name="attendance_void_state_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(voided_at__isnull=True)
                | models.Q(voided_at__gte=models.F("checked_in_at")),
                name="attendance_void_after_checkin",
            ),
        ]

    def __str__(self):
        return f"Attendance for registration #{self.registration_id}"


RATING_FIELDS = (
    "overall_rating", "material_rating", "speaker_rating", "organization_rating",
)


class FeedbackQuerySet(models.QuerySet):
    def eligible(self):
        return self.filter(
            registration__status=RegistrationStatus.REGISTERED,
            registration__event__status=EventStatus.COMPLETED,
            registration__attendance__status=Attendance.Status.PRESENT,
        )


class Feedback(models.Model):
    registration = models.OneToOneField(
        Registration, on_delete=models.PROTECT, related_name="feedback",
    )
    overall_rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    material_rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    speaker_rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    organization_rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(max_length=2000, blank=True)
    suggestion = models.TextField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = FeedbackQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at", "-pk")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(**{f"{field}__gte": 1, f"{field}__lte": 5}),
                name=f"feedback_{field}_range",
            )
            for field in RATING_FIELDS
        ]

    def __str__(self):
        return f"Feedback for registration #{self.registration_id}"
